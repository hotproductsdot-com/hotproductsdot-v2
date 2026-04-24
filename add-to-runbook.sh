#!/bin/bash

# Add commands to RUNBOOK.md interactively or via arguments

RUNBOOK_FILE="./RUNBOOK.md"

# Color codes
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to list available sections
list_sections() {
    echo -e "${BLUE}Available sections:${NC}"
    echo "  1. Quick Start"
    echo "  2. Daily Content Posting"
    echo "  3. Link & Content Checking"
    echo "  4. Dashboard & Monitoring"
    echo "  5. Git Workflows"
    echo "  6. Multi-Step Sequences"
    echo "  7. Troubleshooting"
    echo "  8. Custom Section"
}

# Function to add command to section
add_command() {
    local section=$1
    local command=$2
    local description=$3

    # Create backup
    cp "$RUNBOOK_FILE" "${RUNBOOK_FILE}.backup"

    # Add the command to the appropriate section
    # This is a simple append - in production you'd want more sophisticated insertion

    case $section in
        "Quick Start"|1)
            sed -i "/## 🚀 Quick Start/a\\\\n### $(date +%s)\n\`\`\`bash\n${command}\n\`\`\`\n" "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to Quick Start${NC}"
            ;;
        "Daily Content Posting"|2)
            sed -i "/## 📝 Daily Content Posting/a\\\\n### New Command\n\`\`\`bash\n${command}\n\`\`\`\n" "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to Daily Content Posting${NC}"
            ;;
        "Link & Content Checking"|3)
            sed -i "/## 🔗 Link & Content Checking/a\\\\n### New Command\n\`\`\`bash\n${command}\n\`\`\`\n" "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to Link & Content Checking${NC}"
            ;;
        "Dashboard & Monitoring"|4)
            sed -i "/## 📊 Dashboard & Monitoring/a\\\\n### New Command\n\`\`\`bash\n${command}\n\`\`\`\n" "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to Dashboard & Monitoring${NC}"
            ;;
        "Git Workflows"|5)
            sed -i "/## 🔧 Git Workflows/a\\\\n### New Command\n\`\`\`bash\n${command}\n\`\`\`\n" "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to Git Workflows${NC}"
            ;;
        "Multi-Step Sequences"|6)
            sed -i "/## 📋 Multi-Step Sequences/a\\\\n### New Sequence\n\`\`\`bash\n${command}\n\`\`\`\n" "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to Multi-Step Sequences${NC}"
            ;;
        "Troubleshooting"|7)
            sed -i "/## 🔍 Troubleshooting/a\\\\n### New Command\n\`\`\`bash\n${command}\n\`\`\`\n" "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to Troubleshooting${NC}"
            ;;
        *)
            echo -e "${YELLOW}Section not found. Appending to end instead...${NC}"
            echo "" >> "$RUNBOOK_FILE"
            echo "### $description" >> "$RUNBOOK_FILE"
            echo '```bash' >> "$RUNBOOK_FILE"
            echo "$command" >> "$RUNBOOK_FILE"
            echo '```' >> "$RUNBOOK_FILE"
            echo -e "${GREEN}✓ Added to end of file${NC}"
            ;;
    esac
}

# Interactive mode
if [ $# -eq 0 ]; then
    echo -e "${BLUE}=== Add Command to RUNBOOK ===${NC}\n"

    list_sections
    echo ""
    read -p "Select section (1-8 or name): " section_choice

    echo ""
    read -p "Enter the command: " command

    echo ""
    read -p "Enter a description (optional): " description

    if [ -z "$description" ]; then
        description="New Command"
    fi

    add_command "$section_choice" "$command" "$description"

    echo -e "\n${GREEN}Done!${NC}"
    echo "Backup saved to: ${RUNBOOK_FILE}.backup"

# Command line mode
elif [ $# -ge 2 ]; then
    section=$1
    command=$2
    description=${3:-"New Command"}

    add_command "$section" "$command" "$description"
    echo "Backup saved to: ${RUNBOOK_FILE}.backup"

else
    echo "Usage:"
    echo "  Interactive:  ./add-to-runbook.sh"
    echo "  Direct:       ./add-to-runbook.sh <section> '<command>' '[description]'"
    echo ""
    echo "Example:"
    echo "  ./add-to-runbook.sh 2 'python3 post_daily.py --new-flag' 'New posting feature'"
fi
