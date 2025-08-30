import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

import { OptionsWithUri } from 'request';

export class Goszakup implements INodeType {
	description: INodeTypeDescription = {
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
		requestDefaults: {
			baseURL: 'https://ows.goszakup.gov.kz',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
			},
		},
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
					{
						name: 'Plans',
						value: 'plans',
					},
					{
						name: 'Subjects',
						value: 'subjects',
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
						resource: ['lots'],
					},
				},
				options: [
					{
						name: 'Get All',
						value: 'getAll',
						description: 'Get all lots',
						action: 'Get all lots',
					},
					{
						name: 'Get by ID',
						value: 'get',
						description: 'Get a lot by ID',
						action: 'Get a lot by ID',
					},
					{
						name: 'Search',
						value: 'search',
						description: 'Search lots',
						action: 'Search lots',
					},
				],
				default: 'getAll',
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['tenders'],
					},
				},
				options: [
					{
						name: 'Get All',
						value: 'getAll',
						description: 'Get all tenders',
						action: 'Get all tenders',
					},
					{
						name: 'Get by ID',
						value: 'get',
						description: 'Get a tender by ID',
						action: 'Get a tender by ID',
					},
					{
						name: 'Search',
						value: 'search',
						description: 'Search tenders',
						action: 'Search tenders',
					},
				],
				default: 'getAll',
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['plans'],
					},
				},
				options: [
					{
						name: 'Get All',
						value: 'getAll',
						description: 'Get all plans',
						action: 'Get all plans',
					},
					{
						name: 'Get by ID',
						value: 'get',
						description: 'Get a plan by ID',
						action: 'Get a plan by ID',
					},
				],
				default: 'getAll',
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['subjects'],
					},
				},
				options: [
					{
						name: 'Get All',
						value: 'getAll',
						description: 'Get all subjects',
						action: 'Get all subjects',
					},
					{
						name: 'Get by BIN',
						value: 'getByBin',
						description: 'Get a subject by BIN',
						action: 'Get a subject by BIN',
					},
				],
				default: 'getAll',
			},
			// ID parameter
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
			// BIN parameter
			{
				displayName: 'BIN',
				name: 'bin',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['getByBin'],
					},
				},
				default: '',
				description: 'BIN of the subject to retrieve',
			},
			// Search parameters
			{
				displayName: 'Search Query',
				name: 'query',
				type: 'string',
				displayOptions: {
					show: {
						operation: ['search'],
					},
				},
				default: '',
				description: 'Search query string',
			},
			// Pagination
			{
				displayName: 'Return All',
				name: 'returnAll',
				type: 'boolean',
				displayOptions: {
					show: {
						operation: ['getAll', 'search'],
					},
				},
				default: false,
				description: 'Whether to return all results or only up to a given limit',
			},
			{
				displayName: 'Limit',
				name: 'limit',
				type: 'number',
				displayOptions: {
					show: {
						operation: ['getAll', 'search'],
						returnAll: [false],
					},
				},
				typeOptions: {
					minValue: 1,
				},
				default: 50,
				description: 'Max number of results to return',
			},
			// Filters
			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				displayOptions: {
					show: {
						operation: ['getAll', 'search'],
					},
				},
				options: [
					{
						displayName: 'Date From',
						name: 'dateFrom',
						type: 'dateTime',
						default: '',
						description: 'Filter from date',
					},
					{
						displayName: 'Date To',
						name: 'dateTo',
						type: 'dateTime',
						default: '',
						description: 'Filter to date',
					},
					{
						displayName: 'Status',
						name: 'status',
						type: 'options',
						options: [
							{
								name: 'Published',
								value: 'published',
							},
							{
								name: 'Active',
								value: 'active',
							},
							{
								name: 'Completed',
								value: 'completed',
							},
							{
								name: 'Cancelled',
								value: 'cancelled',
							},
						],
						default: '',
						description: 'Filter by status',
					},
				],
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const resource = this.getNodeParameter('resource', 0);
		const operation = this.getNodeParameter('operation', 0);

		const credentials = await this.getCredentials('goszakupApi');

		for (let i = 0; i < items.length; i++) {
			try {
				let responseData;

				if (resource === 'lots') {
					responseData = await this.executeLotOperations(operation, i, credentials);
				} else if (resource === 'tenders') {
					responseData = await this.executeTenderOperations(operation, i, credentials);
				} else if (resource === 'plans') {
					responseData = await this.executePlanOperations(operation, i, credentials);
				} else if (resource === 'subjects') {
					responseData = await this.executeSubjectOperations(operation, i, credentials);
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

	private async executeLotOperations(
		operation: string,
		itemIndex: number,
		credentials: any,
	): Promise<any> {
		if (operation === 'getAll') {
			return this.getAllLots(itemIndex, credentials);
		} else if (operation === 'get') {
			const id = this.getNodeParameter('id', itemIndex) as string;
			return this.getLotById(id, credentials);
		} else if (operation === 'search') {
			const query = this.getNodeParameter('query', itemIndex) as string;
			return this.searchLots(query, itemIndex, credentials);
		}
	}

	private async executeTenderOperations(
		operation: string,
		itemIndex: number,
		credentials: any,
	): Promise<any> {
		if (operation === 'getAll') {
			return this.getAllTenders(itemIndex, credentials);
		} else if (operation === 'get') {
			const id = this.getNodeParameter('id', itemIndex) as string;
			return this.getTenderById(id, credentials);
		} else if (operation === 'search') {
			const query = this.getNodeParameter('query', itemIndex) as string;
			return this.searchTenders(query, itemIndex, credentials);
		}
	}

	private async executePlanOperations(
		operation: string,
		itemIndex: number,
		credentials: any,
	): Promise<any> {
		if (operation === 'getAll') {
			return this.getAllPlans(itemIndex, credentials);
		} else if (operation === 'get') {
			const id = this.getNodeParameter('id', itemIndex) as string;
			return this.getPlanById(id, credentials);
		}
	}

	private async executeSubjectOperations(
		operation: string,
		itemIndex: number,
		credentials: any,
	): Promise<any> {
		if (operation === 'getAll') {
			return this.getAllSubjects(itemIndex, credentials);
		} else if (operation === 'getByBin') {
			const bin = this.getNodeParameter('bin', itemIndex) as string;
			return this.getSubjectByBin(bin, credentials);
		}
	}

	private async makeRequest(endpoint: string, credentials: any, params?: any): Promise<any> {
		const options: OptionsWithUri = {
			method: 'GET',
			uri: `${credentials.baseUrl}${endpoint}`,
			headers: {
				'Authorization': `Bearer ${credentials.token}`,
				'Accept': 'application/json',
			},
			json: true,
		};

		if (params) {
			options.qs = params;
		}

		try {
			return await this.helpers.request(options);
		} catch (error) {
			throw new NodeOperationError(this.getNode(), `Goszakup API request failed: ${error.message}`);
		}
	}

	private async getAllLots(itemIndex: number, credentials: any): Promise<any> {
		const returnAll = this.getNodeParameter('returnAll', itemIndex);
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const params: any = {};

		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		if (additionalFields.dateFrom) {
			params.date_from = additionalFields.dateFrom;
		}
		if (additionalFields.dateTo) {
			params.date_to = additionalFields.dateTo;
		}
		if (additionalFields.status) {
			params.status = additionalFields.status;
		}

		const response = await this.makeRequest('/v3/lots', credentials, params);
		return returnAll ? response.data || response : (response.data || response).slice(0, params.limit);
	}

	private async getLotById(id: string, credentials: any): Promise<any> {
		return this.makeRequest(`/v3/lots/${id}`, credentials);
	}

	private async searchLots(query: string, itemIndex: number, credentials: any): Promise<any> {
		const returnAll = this.getNodeParameter('returnAll', itemIndex);
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const params: any = { q: query };

		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		if (additionalFields.dateFrom) {
			params.date_from = additionalFields.dateFrom;
		}
		if (additionalFields.dateTo) {
			params.date_to = additionalFields.dateTo;
		}
		if (additionalFields.status) {
			params.status = additionalFields.status;
		}

		const response = await this.makeRequest('/v3/lots/search', credentials, params);
		return returnAll ? response.data || response : (response.data || response).slice(0, params.limit);
	}

	private async getAllTenders(itemIndex: number, credentials: any): Promise<any> {
		const returnAll = this.getNodeParameter('returnAll', itemIndex);
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const params: any = {};

		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		if (additionalFields.dateFrom) {
			params.date_from = additionalFields.dateFrom;
		}
		if (additionalFields.dateTo) {
			params.date_to = additionalFields.dateTo;
		}
		if (additionalFields.status) {
			params.status = additionalFields.status;
		}

		const response = await this.makeRequest('/v3/tenders', credentials, params);
		return returnAll ? response.data || response : (response.data || response).slice(0, params.limit);
	}

	private async getTenderById(id: string, credentials: any): Promise<any> {
		return this.makeRequest(`/v3/tenders/${id}`, credentials);
	}

	private async searchTenders(query: string, itemIndex: number, credentials: any): Promise<any> {
		const returnAll = this.getNodeParameter('returnAll', itemIndex);
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const params: any = { q: query };

		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		if (additionalFields.dateFrom) {
			params.date_from = additionalFields.dateFrom;
		}
		if (additionalFields.dateTo) {
			params.date_to = additionalFields.dateTo;
		}
		if (additionalFields.status) {
			params.status = additionalFields.status;
		}

		const response = await this.makeRequest('/v3/tenders/search', credentials, params);
		return returnAll ? response.data || response : (response.data || response).slice(0, params.limit);
	}

	private async getAllPlans(itemIndex: number, credentials: any): Promise<any> {
		const returnAll = this.getNodeParameter('returnAll', itemIndex);
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const params: any = {};

		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		if (additionalFields.dateFrom) {
			params.date_from = additionalFields.dateFrom;
		}
		if (additionalFields.dateTo) {
			params.date_to = additionalFields.dateTo;
		}

		const response = await this.makeRequest('/v3/plans', credentials, params);
		return returnAll ? response.data || response : (response.data || response).slice(0, params.limit);
	}

	private async getPlanById(id: string, credentials: any): Promise<any> {
		return this.makeRequest(`/v3/plans/${id}`, credentials);
	}

	private async getAllSubjects(itemIndex: number, credentials: any): Promise<any> {
		const returnAll = this.getNodeParameter('returnAll', itemIndex);

		const params: any = {};

		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		const response = await this.makeRequest('/v3/subjects', credentials, params);
		return returnAll ? response.data || response : (response.data || response).slice(0, params.limit);
	}

	private async getSubjectByBin(bin: string, credentials: any): Promise<any> {
		return this.makeRequest(`/v3/subjects/${bin}`, credentials);
	}
}
