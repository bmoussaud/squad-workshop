import ast
import json
from pathlib import Path
import re
import shlex
import subprocess
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INFRASTRUCTURE_ROOT = REPOSITORY_ROOT / "infra"
PROJECT_BICEP_TEMPLATES = tuple(sorted(INFRASTRUCTURE_ROOT.glob("*.bicep")))
EXPECTED_AVM_MODULES = (
    "managed-identity/user-assigned-identity",
    "operational-insights/workspace",
    "insights/component",
    "cognitive-services/account",
    "container-registry/registry",
    "storage/storage-account",
    "app/container-app",
    "network/virtual-network",
    "network/private-endpoint",
    "network/private-dns-zone",
)


def parse_simple_yaml_mapping(source: str) -> dict[str, object]:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    for raw_line in source.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, separator, raw_value = raw_line.strip().partition(":")
        if not separator or not key:
            raise AssertionError(f"Unsupported YAML line: {raw_line!r}")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        value = raw_value.strip()
        if value:
            parent[key] = value.strip("'\"")
        else:
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def extract_bicep_block(source: str, declaration: str, name: str) -> str:
    match = re.search(
        rf"\b{re.escape(declaration)}\s+{re.escape(name)}\b[^=]*=\s*"
        rf"(?:if\s*\([^)]*\)\s*)?\{{",
        source,
    )
    if match is None:
        raise AssertionError(f"Missing Bicep {declaration} {name}")
    opening = source.find("{", match.start())
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening, len(source)):
        character = source[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in ("'", '"'):
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[opening : index + 1]
    raise AssertionError(f"Unterminated Bicep {declaration} {name}")


class DeploymentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.azure = parse_simple_yaml_mapping(
            (REPOSITORY_ROOT / "azure.yaml").read_text(encoding="utf-8")
        )
        cls.dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
        cls.main_bicep = (REPOSITORY_ROOT / "infra/main.bicep").read_text(
            encoding="utf-8"
        )
        cls.web_bicep = (REPOSITORY_ROOT / "infra/web.bicep").read_text(
            encoding="utf-8"
        )
        cls.foundry_bicep = (REPOSITORY_ROOT / "infra/foundry.bicep").read_text(
            encoding="utf-8"
        )
        cls.azure_deployment_design = (
            REPOSITORY_ROOT / "docs/design/azure-deployment.md"
        ).read_text(encoding="utf-8")
        cls.legacy_blob_role_migration = (
            REPOSITORY_ROOT
            / "infra/scripts/retire_legacy_storage_blob_role.py"
        ).read_text(encoding="utf-8")
        compiled_web = subprocess.run(
            ["bicep", "build", str(INFRASTRUCTURE_ROOT / "web.bicep"), "--stdout"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        if compiled_web.returncode:
            raise AssertionError(
                "Bicep compilation failed:\n"
                f"{compiled_web.stdout}\n{compiled_web.stderr}"
            )
        cls.compiled_web_template = json.loads(compiled_web.stdout)

    def test_project_owned_bicep_uses_resource_group_scoped_avms_or_documented_fallbacks(self) -> None:
        templates = {
            template.relative_to(REPOSITORY_ROOT).as_posix(): template.read_text(
                encoding="utf-8"
            )
            for template in PROJECT_BICEP_TEMPLATES
        }
        self.assertEqual(
            set(templates),
            {"infra/foundry.bicep", "infra/main.bicep", "infra/web.bicep"},
        )
        for template_name, template in templates.items():
            self.assertRegex(
                template,
                r"(?m)^targetScope\s*=\s*'resourceGroup'\s*$",
                msg=f"{template_name} must be resource-group scoped",
            )

        avm_references = "\n".join(templates.values())
        for module in EXPECTED_AVM_MODULES:
            self.assertRegex(
                avm_references,
                rf"(?m)^\s*module\s+\w+\s+'br/(?:public:)?avm/res/{re.escape(module)}:\d+\.\d+\.\d+'",
                msg=f"Missing an exact-version AVM reference for {module}",
            )

        self.assertIn("Azure Verified Modules (AVM) first", self.azure_deployment_design)
        self.assertNotIn(
            "Azure Verified Modules (AVM) must not be used", self.azure_deployment_design
        )
        self.assertNotIn(
            "Use native Bicep resource declarations for all project-owned infrastructure.",
            self.azure_deployment_design,
        )

        direct_resources = {
            f"{template_name}/{resource_name}"
            for template_name, template in templates.items()
            for resource_name in re.findall(
            r"(?m)^\s*resource\s+(\w+)\s+'Microsoft\.[^']+'\s*=", template
            )
        }
        documented_fallbacks = set(
            re.findall(
                r"(?m)^<!-- native-bicep-fallback: "
                r"(infra/[\w.-]+\.bicep/\w+) \| Microsoft\.[^|]+ \| .+ -->$",
                self.azure_deployment_design,
            )
        )
        self.assertSetEqual(
            documented_fallbacks,
            direct_resources,
            "Each direct resource must have one documented native-Bicep fallback rationale",
        )

    def test_azd_declares_only_the_approved_web_container_app_service(self) -> None:
        self.assertEqual(self.azure["name"], "fantasy-cards")
        self.assertEqual(self.azure["infra"], {"provider": "bicep", "path": "infra"})
        self.assertEqual(set(self.azure["services"]), {"web"})
        self.assertEqual(
            self.azure["services"]["web"],
            {
                "project": ".",
                "language": "py",
                "host": "containerapp",
                "docker": {"path": "./Dockerfile", "context": "."},
            },
        )

    def test_container_runtime_is_non_root_and_uses_the_approved_entry_point(self) -> None:
        instructions: dict[str, list[str]] = {}
        for line in self.dockerfile.splitlines():
            if not line or line[0].isspace() or line.startswith("#"):
                continue
            instruction, _, value = line.partition(" ")
            instructions.setdefault(instruction.upper(), []).append(value.strip())

        runtime_user = instructions["USER"][-1]
        self.assertNotIn(runtime_user.lower(), {"root", "0", "0:0"})
        self.assertRegex(runtime_user, r"^[1-9]\d*(?::[1-9]\d*)?$")
        self.assertIn("8000", instructions["EXPOSE"][-1].split())
        command = ast.literal_eval(instructions["CMD"][-1])
        self.assertEqual(
            command,
            [
                "uvicorn",
                "fantasy_cards.web:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--workers",
                "1",
                "--limit-concurrency",
                "16",
                "--no-access-log",
            ],
        )

    def test_main_bicep_preserves_module_boundary_and_required_outputs(self) -> None:
        web_module = extract_bicep_block(self.main_bicep, "module", "web")
        self.assertIn("'web.bicep'", self.main_bicep)
        for explicit_input in (
            "applicationIdentityClientId",
            "applicationIdentityPrincipalId",
            "applicationIdentityResourceId",
            "applicationInsightsConnectionString",
            "applicationInsightsResourceId",
            "logAnalyticsWorkspaceResourceId",
        ):
            self.assertIn(explicit_input, web_module)
        outputs = set(re.findall(r"(?m)^output\s+(\w+)\s+", self.main_bicep))
        self.assertTrue(
            {
                "SERVICE_WEB_URI",
                "AZURE_CONTAINER_APP_NAME",
                "AZURE_CONTAINER_APPS_ENVIRONMENT_NAME",
                "AZURE_CONTAINER_REGISTRY_ENDPOINT",
                "AZURE_STORAGE_ACCOUNT_URL",
                "FANTASY_CARD_BLOB_CONTAINER",
                "AZURE_OPENAI_ENDPOINT",
                "AZURE_OPENAI_DEPLOYMENT_NAME",
                "AZURE_CLIENT_ID",
                "APPLICATIONINSIGHTS_CONNECTION_STRING",
            }.issubset(outputs)
        )

    def test_storage_identity_and_rbac_are_private_and_least_privilege(self) -> None:
        storage = extract_bicep_block(self.web_bicep, "module", "storageAccount")
        app = extract_bicep_block(self.web_bicep, "module", "containerApp")
        acr_role = extract_bicep_block(self.web_bicep, "resource", "acrPullAssignment")
        blob_role = extract_bicep_block(self.web_bicep, "resource", "blobDataAssignment")
        telemetry_role = extract_bicep_block(
            self.web_bicep, "resource", "monitoringMetricsPublisherAssignment"
        )

        for contract in (
            "allowBlobPublicAccess: false",
            "allowSharedKeyAccess: false",
            "defaultToOAuthAuthentication: true",
            "supportsHttpsTrafficOnly: true",
            "minimumTlsVersion: 'TLS1_2'",
            "publicNetworkAccess: 'Disabled'",
        ):
            self.assertIn(contract, storage)
        self.assertIn("publicAccess: 'None'", storage)
        self.assertIn("daysAfterCreationGreaterThan: 30", storage)
        self.assertIn("blobTypes:", storage)
        self.assertIn("'blockBlob'", storage)
        self.assertNotIn("roleAssignments:", storage)
        self.assertIn("userAssignedResourceIds:", app)
        self.assertIn("applicationIdentityResourceId", app)
        self.assertIn("scope: containerRegistry", acr_role)
        self.assertIn("acrPullRoleDefinitionId", acr_role)
        self.assertIn("scope: artifactContainer", blob_role)
        self.assertIn("blobDataContributorRoleDefinitionId", blob_role)
        self.assertIn("scope: applicationInsights", telemetry_role)
        self.assertIn("monitoringMetricsPublisherRoleDefinitionId", telemetry_role)
        self.assertIn("3913510d-42f4-4e42-8a64-420c390055eb", self.web_bicep)
        self.assertIn(
            "applicationIdentityPrincipalId", acr_role + blob_role + telemetry_role
        )
        self.assertNotRegex(self.web_bicep, r"(?i)(connectionString|accountKey|sasToken)\s*:")

    def test_legacy_blob_role_retirement_is_manual_maintenance(self) -> None:
        migration = self.legacy_blob_role_migration

        self.assertNotIn("hooks", self.azure)
        self.assertNotIn(
            "retire_legacy_storage_blob_role.py",
            (REPOSITORY_ROOT / "azure.yaml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "output APPLICATION_IDENTITY_PRINCIPAL_ID string",
            self.main_bicep,
        )
        self.assertIn("BLOB_DATA_CONTRIBUTOR_ROLE_ID", migration)
        self.assertIn('"AZURE_STORAGE_ACCOUNT_URL"', migration)
        self.assertIn('"APPLICATION_IDENTITY_PRINCIPAL_ID"', migration)
        self.assertIn(
            'f"{storage_account_id}/blobServices/default/containers/artifacts"',
            migration,
        )
        self.assertIn('"--assignee"', migration)
        self.assertNotIn('"--assignee-object-id"', migration)
        self.assertIn("if len(container_assignment_ids) != 1:", migration)
        self.assertIn("if len(legacy_assignment_ids) != 1:", migration)
        self.assertIn(
            'run_az("role", "assignment", "delete", "--ids", legacy_assignment_ids[0])',
            migration,
        )
        self.assertIn(
            "The legacy account-scoped Storage Blob Data Contributor assignment ",
            migration,
        )
        self.assertIn(
            "remains after retirement.",
            migration,
        )
        self.assertIn(
            "The required container-scoped Storage Blob Data Contributor assignment ",
            migration,
        )
        self.assertIn(
            "is no longer present after retirement.",
            migration,
        )
        self.assertRegex(
            migration,
            r"ARM incremental mode cannot delete a resource\s+that was merely omitted",
        )

    def test_private_blob_connectivity_uses_a_parallel_vnet_environment_and_private_dns(self) -> None:
        virtual_network = extract_bicep_block(
            self.web_bicep, "module", "privateVirtualNetwork"
        )
        private_dns_zone = extract_bicep_block(
            self.web_bicep, "module", "privateDnsZone"
        )
        private_endpoint = extract_bicep_block(
            self.web_bicep, "module", "blobPrivateEndpoint"
        )
        private_environment = extract_bicep_block(
            self.web_bicep, "resource", "privateContainerAppsEnvironment"
        )
        private_app = extract_bicep_block(
            self.web_bicep, "module", "privateContainerApp"
        )
        existing_environment = extract_bicep_block(
            self.web_bicep, "resource", "containerAppsEnvironment"
        )
        existing_app = extract_bicep_block(self.web_bicep, "module", "containerApp")

        self.assertIn(
            "br/public:avm/res/network/virtual-network:0.9.0", self.web_bicep
        )
        self.assertIn(
            "br/public:avm/res/network/private-endpoint:0.9.1", self.web_bicep
        )
        self.assertIn(
            "br/public:avm/res/network/private-dns-zone:0.8.1", self.web_bicep
        )
        for contract in (
            "addressPrefix: '10.30.0.0/27'",
            "delegation: 'Microsoft.App/environments'",
            "addressPrefix: '10.30.0.32/28'",
            "privateEndpointNetworkPolicies: 'Disabled'",
        ):
            self.assertIn(contract, virtual_network)
        self.assertIn("infrastructureSubnetId:", private_environment)
        self.assertIn("internal: false", private_environment)
        self.assertIn("publicNetworkAccess: 'Enabled'", private_environment)
        self.assertIn(
            "environmentResourceId: privateContainerAppsEnvironment.id", private_app
        )
        self.assertIn("ingressExternal: true", private_app)
        self.assertIn("privateLinkServiceId: storageAccountResource.id", private_endpoint)
        self.assertIn("'blob'", private_endpoint)
        self.assertIn("privateDnsZone.outputs.resourceId", private_endpoint)
        self.assertIn(
            "privatelink.blob.${environment().suffixes.storage}", self.web_bicep
        )
        self.assertIn("virtualNetworkResourceId: privateVirtualNetwork.outputs.resourceId", private_dns_zone)
        self.assertNotIn("vnetConfiguration:", existing_environment)
        self.assertIn("environmentResourceId: containerAppsEnvironment.id", existing_app)

    def test_private_container_app_name_uses_an_aca_safe_resource_token(self) -> None:
        private_app = extract_bicep_block(
            self.web_bicep, "module", "privateContainerApp"
        )
        expected_name = "ca-fc-nrp2z4rl3jd32-pvt"

        self.assertIn(
            "var privateContainerAppName = 'ca-fc-${resourceToken}-pvt'",
            self.web_bicep,
        )
        self.assertIn("name: privateContainerAppName", private_app)
        self.assertEqual(len(expected_name), 23)
        self.assertLessEqual(len(expected_name), 32)
        self.assertRegex(expected_name, r"^[a-z][a-z0-9-]*[a-z0-9]$")
        self.assertNotIn("--", expected_name)

    def test_compiled_private_blob_and_rbac_resources_wait_for_avm_deployments(self) -> None:
        resources = self.compiled_web_template["resources"]

        def dependency_text(resource: dict[str, object]) -> str:
            return "\n".join(resource.get("dependsOn", []))

        blob_private_endpoint = next(
            resource
            for resource in resources
            if resource["type"] == "Microsoft.Resources/deployments"
            and "blob-private-endpoint" in resource["name"]
        )
        acr_pull_assignment = next(
            resource
            for resource in resources
            if resource["type"] == "Microsoft.Authorization/roleAssignments"
            and "acrPullRoleDefinitionId" in resource["properties"]["roleDefinitionId"]
        )
        blob_data_assignment = next(
            resource
            for resource in resources
            if resource["type"] == "Microsoft.Authorization/roleAssignments"
            and "blobDataContributorRoleDefinitionId"
            in resource["properties"]["roleDefinitionId"]
        )

        self.assertIn(
            "format('storage-account-{0}', variables('resourceToken'))",
            dependency_text(blob_private_endpoint),
        )
        self.assertIn(
            "format('container-registry-{0}', variables('resourceToken'))",
            dependency_text(acr_pull_assignment),
        )
        self.assertIn(
            "format('storage-account-{0}', variables('resourceToken'))",
            dependency_text(blob_data_assignment),
        )

    def test_container_app_contract_has_ingress_probes_scaling_and_exact_environment(self) -> None:
        app = extract_bicep_block(self.web_bicep, "module", "containerApp")
        for contract in (
            "workloadProfileName: 'dedicated'",
            "ingressAllowInsecure: false",
            "ingressExternal: true",
            "ingressTargetPort: 8000",
            "path: '/health/live'",
            "path: '/health/ready'",
            "scaleMinReplicas: 1",
            "scaleMaxReplicas: 2",
            "concurrentRequests: '1'",
        ):
            self.assertIn(contract, app)
        expected_environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "foundry",
            "FANTASY_CARD_IMAGE_TIMEOUT_SECONDS": "120",
            "FANTASY_CARD_ARTIFACT_STORE": "blob",
            "PORT": "8000",
            "FANTASY_CARD_MAX_GENERATION_CONCURRENCY": "1",
            "FANTASY_CARD_RATE_LIMIT_ATTEMPTS": "10",
            "FANTASY_CARD_RATE_LIMIT_WINDOW_SECONDS": "600",
        }
        for name, value in expected_environment.items():
            self.assertRegex(
                app,
                rf"name:\s*'{re.escape(name)}'\s+value:\s*'{re.escape(value)}'",
            )
        for name in (
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
            "AZURE_CLIENT_ID",
            "AZURE_STORAGE_ACCOUNT_URL",
            "FANTASY_CARD_BLOB_CONTAINER",
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
        ):
            self.assertRegex(app, rf"name:\s*'{name}'\s+value:\s*\S+")

    def test_diagnostics_budget_and_alerts_match_emitted_telemetry_contract(self) -> None:
        for resource in (
            "environmentDiagnostics",
            "privateEnvironmentDiagnostics",
            "appDiagnostics",
            "privateAppDiagnostics",
            "registryDiagnostics",
            "actionGroup",
            "resourceGroupBudget",
            "http5xxAlert",
            "readinessAlert",
            "providerAlert",
            "blobFailureAlert",
            "replicaCeilingAlert",
        ):
            extract_bicep_block(self.web_bicep, "resource", resource)
        budget = extract_bicep_block(self.web_bicep, "resource", "resourceGroupBudget")
        for threshold in (50, 80, 100):
            self.assertRegex(budget, rf"threshold:\s*{threshold}\b")

        provider_alert = extract_bicep_block(self.web_bicep, "resource", "providerAlert")
        blob_alert = extract_bicep_block(self.web_bicep, "resource", "blobFailureAlert")
        web_source = (REPOSITORY_ROOT / "src/fantasy_cards/web.py").read_text(
            encoding="utf-8"
        )
        for telemetry_field in ("error_code", "dependency", "success"):
            self.assertIn(f'"{telemetry_field}"', web_source)
        for error_code in ("rate_limited", "provider_timeout", "provider_unavailable"):
            self.assertIn(error_code, provider_alert)
            self.assertIn(error_code, web_source)
        self.assertIn('Properties["dependency"] == "blob"', blob_alert)
        self.assertIn('Properties["success"] == "false"', blob_alert)


if __name__ == "__main__":
    unittest.main()