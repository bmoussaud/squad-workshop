# Private Container App naming

- **Decision:** Name the private Container App `ca-fc-${resourceToken}-pvt`.
- **Reason:** Container App names are limited to 32 characters. The existing environment-derived suffix can exceed that limit; the lower-case 13-character `uniqueString` resource token keeps the name deterministic and unique. For `nrp2z4rl3jd32`, the name is `ca-fc-nrp2z4rl3jd32-pvt` (23 characters).
- **Impact:** The private managed-environment name remains unchanged because its 38-character current deployment name is within the 60-character managed-environment limit. No existing succeeded resources require cleanup for this naming correction.
