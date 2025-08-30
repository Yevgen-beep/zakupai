const { NodeOperationError } = require('n8n-workflow');

class Goszakup {
	constructor() {
		this.description = {
			displayName: 'Goszakup',
			name: 'goszakup',
			icon: 'file:goszakup.svg',
			group: ['input'],
			version: 1,
			subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
			description: 'Interact with Goszakup.gov.kz API',
			defaults: {
				name: 'Goszakup',
			},
			inputs: ['main'],
			outputs: ['main'],
			credentials: [
				{
					name: 'goszakupApi',
					required: true,
				},
			],
			properties: [
				{
					displayName: 'Resource',
					name: 'resource',
					type: 'options',
					noDataExpression: true,
					options: [
						{
							name: 'Lots',
							value: 'lots',
						},
						{
							name: 'Tenders',
							value: 'tenders',
						},
					],
					default: 'lots',
				},
				{
					displayName: 'Operation',
					name: 'operation',
					type: 'options',
					noDataExpression: true,
					displayOptions: {
						show: {
							resource: ['lots', 'tenders'],
						},
					},
					options: [
						{
							name: 'Get All',
							value: 'getAll',
							description: 'Get all items',
							action: 'Get all items',
						},
						{
							name: 'Get by ID',
							value: 'get',
							description: 'Get an item by ID',
							action: 'Get an item by ID',
						},
					],
					default: 'getAll',
				},
				{
					displayName: 'ID',
					name: 'id',
					type: 'string',
					required: true,
					displayOptions: {
						show: {
							operation: ['get'],
						},
					},
					default: '',
					description: 'ID of the item to retrieve',
				},
				{
					displayName: 'Limit',
					name: 'limit',
					type: 'number',
					displayOptions: {
						show: {
							operation: ['getAll'],
						},
					},
					typeOptions: {
						minValue: 1,
					},
					default: 10,
					description: 'Max number of results to return',
				},
			],
		};
	}

	async execute() {
		const items = this.getInputData();
		const returnData = [];

		const resource = this.getNodeParameter('resource', 0);
		const operation = this.getNodeParameter('operation', 0);

		const credentials = await this.getCredentials('goszakupApi');

		for (let i = 0; i < items.length; i++) {
			try {
				let responseData;

				if (resource === 'lots') {
					if (operation === 'getAll') {
						const limit = this.getNodeParameter('limit', i);
						responseData = await this.makeRequest('/v3/lots', credentials, { limit });
					} else if (operation === 'get') {
						const id = this.getNodeParameter('id', i);
						responseData = await this.makeRequest(`/v3/lots/${id}`, credentials);
					}
				} else if (resource === 'tenders') {
					if (operation === 'getAll') {
						const limit = this.getNodeParameter('limit', i);
						responseData = await this.makeRequest('/v3/tenders', credentials, { limit });
					} else if (operation === 'get') {
						const id = this.getNodeParameter('id', i);
						responseData = await this.makeRequest(`/v3/tenders/${id}`, credentials);
					}
				}

				if (Array.isArray(responseData)) {
					returnData.push(...responseData.map((item) => ({ json: item })));
				} else {
					returnData.push({ json: responseData });
				}
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({ json: { error: error.message } });
					continue;
				}
				throw error;
			}
		}

		return [returnData];
	}

	async makeRequest(endpoint, credentials, params = {}) {
		const options = {
			method: 'GET',
			uri: `${credentials.baseUrl}${endpoint}`,
			headers: {
				'Authorization': `Bearer ${credentials.token}`,
				'Accept': 'application/json',
			},
			json: true,
		};

		if (params && Object.keys(params).length > 0) {
			options.qs = params;
		}

		try {
			return await this.helpers.request(options);
		} catch (error) {
			throw new NodeOperationError(this.getNode(), `Goszakup API request failed: ${error.message}`);
		}
	}
}

module.exports = { Goszakup };
