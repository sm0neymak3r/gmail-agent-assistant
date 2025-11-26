#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PROJECT_ID="gmail-agent-prod"
REGION="us-central1"
TERRAFORM_SA_KEY="$HOME/gmail-agent-keys/terraform-sa-key.json"

echo -e "${GREEN}Gmail Agent Infrastructure Deployment${NC}"
echo "======================================="

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"
if [ ! -f "$TERRAFORM_SA_KEY" ]; then
    echo -e "${RED}Error: Terraform service account key not found at $TERRAFORM_SA_KEY${NC}"
    exit 1
fi

# Set up authentication
export GOOGLE_APPLICATION_CREDENTIALS="$TERRAFORM_SA_KEY"

# Navigate to infrastructure directory
cd infrastructure/

# Initialize Terraform with workspace
echo -e "\n${YELLOW}Initializing Terraform...${NC}"
terraform init

# Check if workspace exists, create if not
WORKSPACE="${1:-dev}"
if ! terraform workspace list | grep -q "$WORKSPACE"; then
    echo -e "${YELLOW}Creating workspace: $WORKSPACE${NC}"
    terraform workspace new "$WORKSPACE"
else
    echo -e "${YELLOW}Selecting workspace: $WORKSPACE${NC}"
    terraform workspace select "$WORKSPACE"
fi

# Create tfvars file if it doesn't exist
if [ ! -f "terraform.tfvars" ]; then
    echo -e "${YELLOW}Creating terraform.tfvars from example...${NC}"
    cp terraform.tfvars.example terraform.tfvars
    echo "environment = \"$WORKSPACE\"" >> terraform.tfvars
fi

# Plan
echo -e "\n${YELLOW}Planning infrastructure changes...${NC}"
terraform plan -out=tfplan

# Apply
echo -e "\n${YELLOW}Applying infrastructure...${NC}"
read -p "Do you want to apply these changes? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    terraform apply tfplan

    # Output important values
    echo -e "\n${GREEN}Infrastructure deployed successfully!${NC}"
    echo -e "\n${YELLOW}Important outputs:${NC}"
    terraform output

    echo -e "\n${YELLOW}Next steps:${NC}"
    echo "1. Add API keys to Secret Manager:"
    echo "   - Anthropic API key: anthropic-api-key-$WORKSPACE"
    echo ""
    echo "2. Initialize database schema:"
    echo "   - Review /tmp/schema.sql"
    echo "   - Connect to Cloud SQL and apply schema"
    echo ""
    echo "3. Build and deploy application:"
    echo "   - Build Docker image"
    echo "   - Push to Artifact Registry"
    echo "   - Update Cloud Run service"
else
    echo -e "${RED}Deployment cancelled${NC}"
    rm tfplan
fi
