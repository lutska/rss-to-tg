# Project Structure

## Directory Layout

```
.
├── terraform/          # Terraform infrastructure code
│   ├── main.tf        # Main resource definitions
│   └── variables.tf   # Variable declarations
├── .kiro/             # Kiro AI assistant configuration
│   └── steering/      # AI guidance documents
└── README             # Project documentation
```

## Conventions

### Terraform Organization
- `main.tf`: Contains provider configuration and resource definitions
- `variables.tf`: Declares all input variables with types, defaults, and descriptions
- Resources follow AWS naming conventions with descriptive identifiers

### Naming Patterns
- S3 buckets: Use descriptive names with project context (e.g., `rsschool-first-task-bucket`)
- Variables: Use lowercase with underscores (e.g., `regions`)

## File Placement Rules
- All Terraform files belong in the `terraform/` directory
- Infrastructure code should be modular and organized by resource type for larger projects
- Variable defaults should be appropriate for the primary use case (eu-west-1 region)
