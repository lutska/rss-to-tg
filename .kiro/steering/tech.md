# Technology Stack

## Infrastructure as Code
- **Terraform**: Primary IaC tool for AWS resource provisioning
- **AWS Provider**: hashicorp/aws (version not pinned)

## Cloud Platform
- **AWS**: Target cloud platform
- Default region: eu-west-1 (configurable via variables)

## Common Commands

### Terraform Operations
```bash
# Initialize Terraform working directory
terraform init

# Validate configuration files
terraform validate

# Preview changes
terraform plan

# Apply infrastructure changes
terraform apply

# Destroy infrastructure
terraform destroy

# Format Terraform files
terraform fmt
```

## Best Practices
- Always run `terraform plan` before `terraform apply`
- Use variables for configurable values (regions, resource names, etc.)
- Keep state files secure and consider remote state for team collaboration
