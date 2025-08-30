#!/usr/bin/env node

/**
 * Тестовый скрипт для проверки функциональности goszakup ноды
 */

// Эмуляция контекста n8n
const mockContext = {
    getInputData: () => [{ json: {} }],
    getNodeParameter: (name, index) => {
        const params = {
            resource: 'lots',
            operation: 'getAll',
            limit: 5
        };
        return params[name];
    },
    getCredentials: async () => ({
        token: process.env.GOSZAKUP_TOKEN || 'test-token',
        baseUrl: process.env.GOSZAKUP_BASE || 'https://ows.goszakup.gov.kz'
    }),
    helpers: {
        request: async (options) => {
            console.log(`🔍 Making request to: ${options.uri}`);
            console.log(`📋 Headers:`, options.headers);
            console.log(`📊 Query params:`, options.qs || 'none');

            // Имитируем ответ API
            return {
                data: [
                    {
                        id: '12345',
                        title: 'Тестовый лот',
                        status: 'active',
                        price: 1000000,
                        deadline: '2024-12-31'
                    },
                    {
                        id: '67890',
                        title: 'Другой тестовый лот',
                        status: 'published',
                        price: 500000,
                        deadline: '2024-11-30'
                    }
                ]
            };
        }
    },
    continueOnFail: () => false,
    getNode: () => ({ name: 'Test Goszakup Node' })
};

async function testGoszakupNode() {
    console.log('🚀 Testing Goszakup n8n Node');
    console.log('================================\n');

    try {
        // Загружаем нашу ноду (предполагая что мы в правильной директории)
        const GoszakupNodePath = './n8n-nodes/goszakup-rk/nodes/Goszakup/Goszakup.node.js';

        // Проверяем существование файла
        const fs = require('fs');
        if (!fs.existsSync(GoszakupNodePath)) {
            console.error('❌ Файл ноды не найден:', GoszakupNodePath);
            return;
        }

        const { Goszakup } = require(GoszakupNodePath);
        const node = new Goszakup();

        console.log('✅ Нода успешно загружена');
        console.log(`📋 Название: ${node.description.displayName}`);
        console.log(`🔧 Версия: ${node.description.version}`);
        console.log(`📝 Описание: ${node.description.description}\n`);

        // Привязываем контекст к ноде
        Object.setPrototypeOf(node, mockContext);
        Object.assign(node, mockContext);

        console.log('🔄 Выполняем тестовый запрос...\n');

        // Выполняем ноду
        const result = await node.execute();

        console.log('✅ Выполнение успешно!');
        console.log(`📊 Получено записей: ${result[0].length}`);
        console.log('📋 Результат:');

        result[0].forEach((item, index) => {
            console.log(`  ${index + 1}. ${item.json.title || item.json.id} (${item.json.status})`);
        });

        console.log('\n🎯 Тест завершён успешно!');

    } catch (error) {
        console.error('❌ Ошибка при тестировании:', error.message);
        console.error('🔍 Stack trace:', error.stack);
    }
}

async function testCredentials() {
    console.log('\n🔐 Testing Credentials');
    console.log('=======================');

    try {
        const CredentialsPath = './n8n-nodes/goszakup-rk/credentials/GoszakupApi.credentials.js';

        if (!require('fs').existsSync(CredentialsPath)) {
            console.error('❌ Файл credentials не найден:', CredentialsPath);
            return;
        }

        const { GoszakupApi } = require(CredentialsPath);
        const credentials = new GoszakupApi();

        console.log('✅ Credentials успешно загружены');
        console.log(`📋 Название: ${credentials.displayName}`);
        console.log(`🔧 Тип: ${credentials.name}`);
        console.log(`📄 Документация: ${credentials.documentationUrl}`);
        console.log(`⚙️  Свойств: ${credentials.properties.length}`);

    } catch (error) {
        console.error('❌ Ошибка при тестировании credentials:', error.message);
    }
}

async function main() {
    await testCredentials();
    await testGoszakupNode();

    console.log('\n📋 Следующие шаги:');
    console.log('1. Откройте n8n: http://localhost:5678');
    console.log('2. Создайте новый workflow');
    console.log('3. Добавьте ноду "Goszakup"');
    console.log('4. Настройте credentials с реальным API токеном');
    console.log('5. Протестируйте с реальными данными');
}

if (require.main === module) {
    main().catch(console.error);
}
