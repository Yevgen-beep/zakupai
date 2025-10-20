#!/bin/bash

set -e

echo "🔄 Setting up ZakupAI Workflows..."

# Check if Docker and Docker Compose are available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p workflows/n8n/backups
mkdir -p workflows/flowise/backups
mkdir -p logs/n8n
mkdir -p logs/flowise

# Copy environment file if it doesn't exist
if [ ! -f .env.workflows ]; then
    echo "⚙️ Creating .env.workflows from template..."
    cp .env.workflows.template .env.workflows 2>/dev/null || echo "Please configure .env.workflows manually"
else
    echo "✅ .env.workflows already exists"
fi

# Initialize PostgreSQL schema for n8n
echo "🗄️ Setting up n8n database schema..."
docker-compose exec -T db psql -U postgres -d zakupai -c "CREATE SCHEMA IF NOT EXISTS n8n;" || true

# Start workflow services
echo "🚀 Starting workflow services..."
docker-compose -f docker-compose.workflows.yml --env-file .env.workflows up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Health check for n8n
echo "🔍 Checking n8n health..."
for i in {1..10}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz | grep -q "200"; then
        echo "✅ n8n is healthy"
        break
    elif [ $i -eq 10 ]; then
        echo "❌ n8n health check failed"
        docker-compose -f docker-compose.workflows.yml logs n8n
    else
        echo "⏳ Waiting for n8n... (attempt $i/10)"
        sleep 10
    fi
done

# Health check for Flowise
echo "🔍 Checking Flowise health..."
for i in {1..10}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/v1/ping | grep -q "200"; then
        echo "✅ Flowise is healthy"
        break
    elif [ $i -eq 10 ]; then
        echo "❌ Flowise health check failed"
        docker-compose -f docker-compose.workflows.yml logs flowise
    else
        echo "⏳ Waiting for Flowise... (attempt $i/10)"
        sleep 10
    fi
done

# Import n8n workflows (if available)
echo "📤 Importing n8n workflows..."
if [ -d workflows/n8n ] && [ "$(ls -A workflows/n8n/*.json 2>/dev/null)" ]; then
    echo "Found workflow files to import:"
    ls -1 workflows/n8n/*.json
    echo "⚠️ Please import these manually through the n8n UI at http://localhost:5678"
else
    echo "ℹ️ No n8n workflow files found to import"
fi

# Import Flowise chatflows (if available)
echo "📤 Importing Flowise chatflows..."
if [ -d workflows/flowise ] && [ "$(ls -A workflows/flowise/*.json 2>/dev/null)" ]; then
    echo "Found chatflow files to import:"
    ls -1 workflows/flowise/*.json
    echo "⚠️ Please import these manually through the Flowise UI at http://localhost:3000"
else
    echo "ℹ️ No Flowise chatflow files found to import"
fi

echo ""
echo "🎉 ZakupAI Workflows setup complete!"
echo ""
echo "📋 Access URLs:"
echo "   n8n Workflows:    http://localhost:5678"
echo "   Flowise AI:       http://localhost:3000"
echo ""
echo "🔐 Default credentials:"
echo "   Username: admin"
echo "   Password: zakupai2024!"
echo ""
echo "📝 Next steps:"
echo "   1. Configure API keys in .env.workflows"
echo "   2. Import workflow files through web interfaces"
echo "   3. Set up Telegram bot credentials"
echo "   4. Test webhook endpoints"
echo ""
echo "📖 For detailed setup instructions, see workflows/README.md"
