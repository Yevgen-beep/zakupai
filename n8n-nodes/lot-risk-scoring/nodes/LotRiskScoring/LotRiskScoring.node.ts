import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

export class LotRiskScoring implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Lot Risk Scoring',
		name: 'lotRiskScoring',
		icon: 'file:lot-risk-scoring.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Evaluate risk scores for tender lots',
		defaults: {
			name: 'Lot Risk Scoring',
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
						name: 'Calculate Risk Score',
						value: 'calculateRisk',
						description: 'Calculate risk score for a lot',
						action: 'Calculate risk score',
					},
					{
						name: 'Explain Risk',
						value: 'explainRisk',
						description: 'Get detailed risk explanation for a lot',
						action: 'Explain risk factors',
					},
					{
						name: 'Get Risk History',
						value: 'getRiskHistory',
						description: 'Get risk evaluation history for a lot',
						action: 'Get risk history',
					},
					{
						name: 'Batch Risk Scoring',
						value: 'batchRiskScoring',
						description: 'Calculate risk scores for multiple lots',
						action: 'Batch risk scoring',
					},
					{
						name: 'Get Risk Factors',
						value: 'getRiskFactors',
						description: 'Get available risk factors and weights',
						action: 'Get risk factors',
					},
					{
						name: 'Update Risk Weights',
						value: 'updateRiskWeights',
						description: 'Update risk factor weights',
						action: 'Update risk weights',
					},
				],
				default: 'calculateRisk',
			},
			// Lot ID parameter
			{
				displayName: 'Lot ID',
				name: 'lotId',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['calculateRisk', 'explainRisk', 'getRiskHistory'],
					},
				},
				default: '',
				description: 'ID of the lot to evaluate',
			},
			// Lot data for calculation
			{
				displayName: 'Lot Data',
				name: 'lotData',
				type: 'json',
				displayOptions: {
					show: {
						operation: ['calculateRisk'],
					},
				},
				default: '{}',
				description: 'Lot data for risk calculation (JSON format)',
			},
			// Batch lot IDs
			{
				displayName: 'Lot IDs',
				name: 'lotIds',
				type: 'string',
				displayOptions: {
					show: {
						operation: ['batchRiskScoring'],
					},
				},
				default: '',
				description: 'Comma-separated list of lot IDs to evaluate',
			},
			// Risk weights update
			{
				displayName: 'Risk Weights',
				name: 'riskWeights',
				type: 'json',
				displayOptions: {
					show: {
						operation: ['updateRiskWeights'],
					},
				},
				default: '{}',
				description: 'Risk factor weights (JSON format)',
			},
			// Risk calculation options
			{
				displayName: 'Risk Options',
				name: 'riskOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: {
					show: {
						operation: ['calculateRisk', 'batchRiskScoring'],
					},
				},
				options: [
					{
						displayName: 'Include Explanation',
						name: 'includeExplanation',
						type: 'boolean',
						default: false,
						description: 'Include risk explanation in response',
					},
					{
						displayName: 'Risk Threshold',
						name: 'riskThreshold',
						type: 'number',
						default: 0.5,
						description: 'Risk threshold for flagging (0-1)',
						typeOptions: {
							minValue: 0,
							maxValue: 1,
						},
					},
					{
						displayName: 'Force Recalculation',
						name: 'forceRecalc',
						type: 'boolean',
						default: false,
						description: 'Force recalculation even if score exists',
					},
					{
						displayName: 'Save Result',
						name: 'saveResult',
						type: 'boolean',
						default: true,
						description: 'Save risk score to database',
					},
				],
			},
			// History options
			{
				displayName: 'History Options',
				name: 'historyOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: {
					show: {
						operation: ['getRiskHistory'],
					},
				},
				options: [
					{
						displayName: 'Date From',
						name: 'dateFrom',
						type: 'dateTime',
						default: '',
						description: 'Filter history from this date',
					},
					{
						displayName: 'Date To',
						name: 'dateTo',
						type: 'dateTime',
						default: '',
						description: 'Filter history until this date',
					},
					{
						displayName: 'Limit',
						name: 'limit',
						type: 'number',
						default: 50,
						description: 'Maximum number of history records',
						typeOptions: {
							minValue: 1,
						},
					},
				],
			},
			// Explanation options
			{
				displayName: 'Explanation Options',
				name: 'explanationOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: {
					show: {
						operation: ['explainRisk'],
					},
				},
				options: [
					{
						displayName: 'Language',
						name: 'language',
						type: 'options',
						options: [
							{
								name: 'Russian',
								value: 'ru',
							},
							{
								name: 'Kazakh',
								value: 'kz',
							},
							{
								name: 'English',
								value: 'en',
							},
						],
						default: 'ru',
						description: 'Language for risk explanation',
					},
					{
						displayName: 'Detail Level',
						name: 'detailLevel',
						type: 'options',
						options: [
							{
								name: 'Summary',
								value: 'summary',
							},
							{
								name: 'Detailed',
								value: 'detailed',
							},
							{
								name: 'Full',
								value: 'full',
							},
						],
						default: 'detailed',
						description: 'Level of detail in explanation',
					},
				],
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
					case 'calculateRisk':
						responseData = await this.calculateRisk(i, credentials);
						break;
					case 'explainRisk':
						responseData = await this.explainRisk(i, credentials);
						break;
					case 'getRiskHistory':
						responseData = await this.getRiskHistory(i, credentials);
						break;
					case 'batchRiskScoring':
						responseData = await this.batchRiskScoring(i, credentials);
						break;
					case 'getRiskFactors':
						responseData = await this.getRiskFactors(credentials);
						break;
					case 'updateRiskWeights':
						responseData = await this.updateRiskWeights(i, credentials);
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
			throw new NodeOperationError(this.getNode(), `Risk Scoring API request failed: ${error.message}`);
		}
	}

	private async calculateRisk(itemIndex: number, credentials: any): Promise<any> {
		const lotId = this.getNodeParameter('lotId', itemIndex) as string;
		const lotData = this.getNodeParameter('lotData', itemIndex) as string;
		const riskOptions = this.getNodeParameter('riskOptions', itemIndex) as any;

		const body: any = {};

		if (lotData && lotData !== '{}') {
			try {
				body.lot_data = JSON.parse(lotData);
			} catch (error) {
				throw new NodeOperationError(this.getNode(), 'Invalid JSON in lot data');
			}
		}

		if (riskOptions.includeExplanation) {
			body.include_explanation = riskOptions.includeExplanation;
		}
		if (riskOptions.riskThreshold) {
			body.risk_threshold = riskOptions.riskThreshold;
		}
		if (riskOptions.forceRecalc) {
			body.force_recalc = riskOptions.forceRecalc;
		}
		if (riskOptions.saveResult !== undefined) {
			body.save_result = riskOptions.saveResult;
		}

		return this.makeRequest(`/risk/score/${lotId}`, credentials, 'POST', body);
	}

	private async explainRisk(itemIndex: number, credentials: any): Promise<any> {
		const lotId = this.getNodeParameter('lotId', itemIndex) as string;
		const explanationOptions = this.getNodeParameter('explanationOptions', itemIndex) as any;

		const params: any = {};
		if (explanationOptions.language) {
			params.lang = explanationOptions.language;
		}
		if (explanationOptions.detailLevel) {
			params.detail = explanationOptions.detailLevel;
		}

		const queryString = Object.keys(params).length > 0 ? '?' + new URLSearchParams(params).toString() : '';
		return this.makeRequest(`/risk/explain/${lotId}${queryString}`, credentials);
	}

	private async getRiskHistory(itemIndex: number, credentials: any): Promise<any> {
		const lotId = this.getNodeParameter('lotId', itemIndex) as string;
		const historyOptions = this.getNodeParameter('historyOptions', itemIndex) as any;

		const params: any = {};
		if (historyOptions.dateFrom) {
			params.date_from = historyOptions.dateFrom;
		}
		if (historyOptions.dateTo) {
			params.date_to = historyOptions.dateTo;
		}
		if (historyOptions.limit) {
			params.limit = historyOptions.limit;
		}

		const queryString = Object.keys(params).length > 0 ? '?' + new URLSearchParams(params).toString() : '';
		return this.makeRequest(`/risk/history/${lotId}${queryString}`, credentials);
	}

	private async batchRiskScoring(itemIndex: number, credentials: any): Promise<any> {
		const lotIds = this.getNodeParameter('lotIds', itemIndex) as string;
		const riskOptions = this.getNodeParameter('riskOptions', itemIndex) as any;

		const lotIdArray = lotIds.split(',').map(id => id.trim()).filter(id => id);
		if (lotIdArray.length === 0) {
			throw new NodeOperationError(this.getNode(), 'No lot IDs provided');
		}

		const body: any = {
			lot_ids: lotIdArray,
		};

		if (riskOptions.includeExplanation) {
			body.include_explanation = riskOptions.includeExplanation;
		}
		if (riskOptions.riskThreshold) {
			body.risk_threshold = riskOptions.riskThreshold;
		}
		if (riskOptions.forceRecalc) {
			body.force_recalc = riskOptions.forceRecalc;
		}
		if (riskOptions.saveResult !== undefined) {
			body.save_result = riskOptions.saveResult;
		}

		return this.makeRequest('/risk/batch-score', credentials, 'POST', body);
	}

	private async getRiskFactors(credentials: any): Promise<any> {
		return this.makeRequest('/risk/factors', credentials);
	}

	private async updateRiskWeights(itemIndex: number, credentials: any): Promise<any> {
		const riskWeights = this.getNodeParameter('riskWeights', itemIndex) as string;

		let weightsData;
		try {
			weightsData = JSON.parse(riskWeights);
		} catch (error) {
			throw new NodeOperationError(this.getNode(), 'Invalid JSON in risk weights');
		}

		return this.makeRequest('/risk/weights', credentials, 'PUT', weightsData);
	}
}
