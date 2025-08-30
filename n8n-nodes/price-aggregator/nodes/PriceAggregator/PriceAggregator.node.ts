import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

export class PriceAggregator implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Price Aggregator',
		name: 'priceAggregator',
		icon: 'file:price-aggregator.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Aggregate and manage pricing data from multiple sources',
		defaults: {
			name: 'Price Aggregator',
		},
		inputs: ['main'],
		outputs: ['main'],
		credentials: [
			{
				name: 'zakupaiApi',
				required: true,
			},
		],
		requestDefaults: {
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
			},
		},
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Upload Price Data',
						value: 'uploadPrices',
						description: 'Upload price data from CSV/XLSX file',
						action: 'Upload price data',
					},
					{
						name: 'Get Price by SKU',
						value: 'getPriceBySku',
						description: 'Get price information for a specific SKU',
						action: 'Get price by SKU',
					},
					{
						name: 'Search Prices',
						value: 'searchPrices',
						description: 'Search prices by various criteria',
						action: 'Search prices',
					},
					{
						name: 'Get Price Sources',
						value: 'getPriceSources',
						description: 'Get all available price sources',
						action: 'Get price sources',
					},
					{
						name: 'Match Lot Prices',
						value: 'matchLotPrices',
						description: 'Match lot items with available prices',
						action: 'Match lot prices',
					},
					{
						name: 'Calculate Lot Total',
						value: 'calculateLotTotal',
						description: 'Calculate total price for a lot',
						action: 'Calculate lot total',
					},
				],
				default: 'getPriceBySku',
			},
			// SKU parameter
			{
				displayName: 'SKU',
				name: 'sku',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['getPriceBySku'],
					},
				},
				default: '',
				description: 'SKU code to lookup',
			},
			// Lot ID parameter
			{
				displayName: 'Lot ID',
				name: 'lotId',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['matchLotPrices', 'calculateLotTotal'],
					},
				},
				default: '',
				description: 'Lot ID for price matching/calculation',
			},
			// File upload parameters
			{
				displayName: 'File Data',
				name: 'fileData',
				type: 'string',
				typeOptions: {
					alwaysOpenEditWindow: true,
				},
				displayOptions: {
					show: {
						operation: ['uploadPrices'],
					},
				},
				default: '',
				description: 'File content (CSV/XLSX) to upload',
			},
			{
				displayName: 'Source Name',
				name: 'sourceName',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['uploadPrices'],
					},
				},
				default: '',
				description: 'Name of the price source',
			},
			// Search parameters
			{
				displayName: 'Search Query',
				name: 'searchQuery',
				type: 'string',
				displayOptions: {
					show: {
						operation: ['searchPrices'],
					},
				},
				default: '',
				description: 'Search query for prices',
			},
			// Additional options
			{
				displayName: 'Additional Options',
				name: 'additionalOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: {
					show: {
						operation: ['searchPrices', 'getPriceBySku'],
					},
				},
				options: [
					{
						displayName: 'Source Filter',
						name: 'sourceFilter',
						type: 'string',
						default: '',
						description: 'Filter by price source',
					},
					{
						displayName: 'Date From',
						name: 'dateFrom',
						type: 'dateTime',
						default: '',
						description: 'Filter prices captured from this date',
					},
					{
						displayName: 'Date To',
						name: 'dateTo',
						type: 'dateTime',
						default: '',
						description: 'Filter prices captured until this date',
					},
					{
						displayName: 'Min Price',
						name: 'minPrice',
						type: 'number',
						default: 0,
						description: 'Minimum price filter',
					},
					{
						displayName: 'Max Price',
						name: 'maxPrice',
						type: 'number',
						default: 0,
						description: 'Maximum price filter',
					},
				],
			},
			// Pagination
			{
				displayName: 'Return All',
				name: 'returnAll',
				type: 'boolean',
				displayOptions: {
					show: {
						operation: ['searchPrices', 'getPriceSources'],
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
						operation: ['searchPrices', 'getPriceSources'],
						returnAll: [false],
					},
				},
				typeOptions: {
					minValue: 1,
				},
				default: 50,
				description: 'Max number of results to return',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const operation = this.getNodeParameter('operation', 0);
		const credentials = await this.getCredentials('zakupaiApi');

		for (let i = 0; i < items.length; i++) {
			try {
				let responseData;

				switch (operation) {
					case 'uploadPrices':
						responseData = await this.uploadPrices(i, credentials);
						break;
					case 'getPriceBySku':
						responseData = await this.getPriceBySku(i, credentials);
						break;
					case 'searchPrices':
						responseData = await this.searchPrices(i, credentials);
						break;
					case 'getPriceSources':
						responseData = await this.getPriceSources(i, credentials);
						break;
					case 'matchLotPrices':
						responseData = await this.matchLotPrices(i, credentials);
						break;
					case 'calculateLotTotal':
						responseData = await this.calculateLotTotal(i, credentials);
						break;
					default:
						throw new NodeOperationError(this.getNode(), `Unknown operation: ${operation}`);
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

	private async makeRequest(endpoint: string, credentials: any, method = 'GET', body?: any): Promise<any> {
		const options: any = {
			method,
			uri: `${credentials.baseUrl}${endpoint}`,
			headers: {
				'X-API-Key': credentials.apiKey,
				'Accept': 'application/json',
				'Content-Type': 'application/json',
			},
			json: true,
		};

		if (body) {
			options.body = body;
		}

		try {
			return await this.helpers.request(options);
		} catch (error) {
			throw new NodeOperationError(this.getNode(), `Price Aggregator API request failed: ${error.message}`);
		}
	}

	private async uploadPrices(itemIndex: number, credentials: any): Promise<any> {
		const fileData = this.getNodeParameter('fileData', itemIndex) as string;
		const sourceName = this.getNodeParameter('sourceName', itemIndex) as string;

		const body = {
			file_data: fileData,
			source_name: sourceName,
		};

		return this.makeRequest('/prices/upload', credentials, 'POST', body);
	}

	private async getPriceBySku(itemIndex: number, credentials: any): Promise<any> {
		const sku = this.getNodeParameter('sku', itemIndex) as string;
		const additionalOptions = this.getNodeParameter('additionalOptions', itemIndex) as any;

		const params: any = {};

		if (additionalOptions.sourceFilter) {
			params.source = additionalOptions.sourceFilter;
		}
		if (additionalOptions.dateFrom) {
			params.date_from = additionalOptions.dateFrom;
		}
		if (additionalOptions.dateTo) {
			params.date_to = additionalOptions.dateTo;
		}
		if (additionalOptions.minPrice) {
			params.min_price = additionalOptions.minPrice;
		}
		if (additionalOptions.maxPrice) {
			params.max_price = additionalOptions.maxPrice;
		}

		const queryString = Object.keys(params).length > 0 ? '?' + new URLSearchParams(params).toString() : '';
		return this.makeRequest(`/prices/sku/${sku}${queryString}`, credentials);
	}

	private async searchPrices(itemIndex: number, credentials: any): Promise<any> {
		const searchQuery = this.getNodeParameter('searchQuery', itemIndex) as string;
		const returnAll = this.getNodeParameter('returnAll', itemIndex);
		const additionalOptions = this.getNodeParameter('additionalOptions', itemIndex) as any;

		const params: any = {
			q: searchQuery,
		};

		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		if (additionalOptions.sourceFilter) {
			params.source = additionalOptions.sourceFilter;
		}
		if (additionalOptions.dateFrom) {
			params.date_from = additionalOptions.dateFrom;
		}
		if (additionalOptions.dateTo) {
			params.date_to = additionalOptions.dateTo;
		}
		if (additionalOptions.minPrice) {
			params.min_price = additionalOptions.minPrice;
		}
		if (additionalOptions.maxPrice) {
			params.max_price = additionalOptions.maxPrice;
		}

		const queryString = '?' + new URLSearchParams(params).toString();
		return this.makeRequest(`/prices/search${queryString}`, credentials);
	}

	private async getPriceSources(itemIndex: number, credentials: any): Promise<any> {
		const returnAll = this.getNodeParameter('returnAll', itemIndex);

		const params: any = {};
		if (!returnAll) {
			params.limit = this.getNodeParameter('limit', itemIndex);
		}

		const queryString = Object.keys(params).length > 0 ? '?' + new URLSearchParams(params).toString() : '';
		return this.makeRequest(`/prices/sources${queryString}`, credentials);
	}

	private async matchLotPrices(itemIndex: number, credentials: any): Promise<any> {
		const lotId = this.getNodeParameter('lotId', itemIndex) as string;

		return this.makeRequest(`/prices/match-lot/${lotId}`, credentials);
	}

	private async calculateLotTotal(itemIndex: number, credentials: any): Promise<any> {
		const lotId = this.getNodeParameter('lotId', itemIndex) as string;

		return this.makeRequest(`/calc/lot-total/${lotId}`, credentials);
	}
}
