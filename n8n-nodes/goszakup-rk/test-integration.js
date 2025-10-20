#!/usr/bin/env node

/**
 * Скрипт для тестирования интеграции goszakup-rk ноды с n8n
 */

const fs = require('fs');
const path = require('path');

async function testNodeStructure() {
    console.log('🔍 Testing Goszakup n8n node structure...');

    const requiredFiles = [
        'package.json',
        'tsconfig.json',
        'credentials/GoszakupApi.credentials.ts',
        'nodes/Goszakup/Goszakup.node.ts',
        'nodes/Goszakup/goszakup.svg',
        'gulpfile.js',
        'test-workflow.json'
    ];

    let allFilesExist = true;

    for (const file of requiredFiles) {
        const filePath = path.join(__dirname, file);
        if (!fs.existsSync(filePath)) {
            console.error(`❌ Missing file: ${file}`);
            allFilesExist = false;
        } else {
            console.log(`✅ Found: ${file}`);
        }
    }

    return allFilesExist;
}

async function testPackageJson() {
    console.log('\n📦 Testing package.json configuration...');

    const packagePath = path.join(__dirname, 'package.json');
    const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));

    const requiredFields = [
        'name',
        'version',
        'n8n.credentials',
        'n8n.nodes'
    ];

    let configValid = true;

    for (const field of requiredFields) {
        const keys = field.split('.');
        let value = packageJson;

        for (const key of keys) {
            value = value?.[key];
        }

        if (!value) {
            console.error(`❌ Missing package.json field: ${field}`);
            configValid = false;
        } else {
            console.log(`✅ Found package.json field: ${field}`);
        }
    }

    // Check n8n specific config
    if (packageJson.n8n) {
        if (packageJson.n8n.credentials?.length > 0) {
            console.log(`✅ Credentials configured: ${packageJson.n8n.credentials.length}`);
        }
        if (packageJson.n8n.nodes?.length > 0) {
            console.log(`✅ Nodes configured: ${packageJson.n8n.nodes.length}`);
        }
    }

    return configValid;
}

async function testWorkflowIntegration() {
    console.log('\n🔗 Testing workflow integration...');

    try {
        const workflowPath = path.join(__dirname, 'test-workflow.json');
        const workflow = JSON.parse(fs.readFileSync(workflowPath, 'utf8'));

        if (workflow.nodes && workflow.nodes.length > 0) {
            console.log(`✅ Workflow has ${workflow.nodes.length} nodes`);

            const goszakupNodes = workflow.nodes.filter(node =>
                node.type === 'n8n-nodes-goszakup-rk.goszakup'
            );

            if (goszakupNodes.length > 0) {
                console.log(`✅ Found ${goszakupNodes.length} Goszakup nodes in workflow`);

                for (const node of goszakupNodes) {
                    console.log(`  - ${node.name}: ${node.parameters.resource}/${node.parameters.operation}`);
                }

                return true;
            } else {
                console.error('❌ No Goszakup nodes found in test workflow');
                return false;
            }
        } else {
            console.error('❌ Test workflow has no nodes');
            return false;
        }
    } catch (error) {
        console.error(`❌ Error testing workflow: ${error.message}`);
        return false;
    }
}

async function generateInstallationInstructions() {
    console.log('\n📋 Installation Instructions:');
    console.log('1. Copy this directory to n8n custom nodes folder:');
    console.log('   ~/.n8n/custom/');
    console.log('');
    console.log('2. Install dependencies:');
    console.log('   cd ~/.n8n/custom/n8n-nodes-goszakup-rk');
    console.log('   npm install');
    console.log('');
    console.log('3. Build the node:');
    console.log('   npm run build');
    console.log('');
    console.log('4. Restart n8n');
    console.log('');
    console.log('5. Configure Goszakup API credentials in n8n:');
    console.log('   - Go to Settings > Credentials');
    console.log('   - Add "Goszakup API" credential');
    console.log('   - Set API Token and Base URL');
    console.log('');
    console.log('6. Import test-workflow.json to test the node');
}

async function testN8nContainerIntegration() {
    console.log('\n🐳 Testing n8n container integration...');

    try {
        const { exec } = require('child_process');
        const util = require('util');
        const execAsync = util.promisify(exec);

        // Check if n8n container is running
        const { stdout } = await execAsync('docker ps --format "table {{.Names}}\\t{{.Status}}" | grep zakupai-n8n');

        if (stdout.trim()) {
            console.log('✅ n8n container is running');
            console.log(`   Status: ${stdout.trim()}`);
            return true;
        } else {
            console.log('⚠️  n8n container not found or not running');
            return false;
        }
    } catch (error) {
        console.log('⚠️  Could not check n8n container status');
        return false;
    }
}

async function main() {
    console.log('🚀 Goszakup n8n Node Integration Test\n');

    const tests = [
        { name: 'Node Structure', test: testNodeStructure },
        { name: 'Package Configuration', test: testPackageJson },
        { name: 'Workflow Integration', test: testWorkflowIntegration },
        { name: 'N8n Container', test: testN8nContainerIntegration }
    ];

    let allTestsPassed = true;

    for (const { name, test } of tests) {
        try {
            const result = await test();
            if (!result) {
                allTestsPassed = false;
            }
        } catch (error) {
            console.error(`❌ Error in ${name}: ${error.message}`);
            allTestsPassed = false;
        }
    }

    if (allTestsPassed) {
        console.log('\n✅ All tests passed! Goszakup n8n node is ready for integration.');
    } else {
        console.log('\n❌ Some tests failed. Please check the issues above.');
    }

    await generateInstallationInstructions();

    console.log('\n🎯 Next Steps:');
    console.log('1. Mount this node in n8n container volume');
    console.log('2. Configure Goszakup API credentials');
    console.log('3. Test with real API calls');
    console.log('4. Create production workflows');
}

if (require.main === module) {
    main().catch(console.error);
}
