import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

import { OptionsWithUri } from 'request';

export class TenderFinanceCalc implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Tender Finance Calc',
		name: 'tenderFinanceCalc',
		icon: 'file:tender-calc.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Calculate tender finance metrics (ROI, margin, profitability)',
		defaults: {
			name: 'Tender Finance Calc',
		},
		inputs: ['main'],
		outputs: ['main'],
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Calculate VAT',
						value: 'vat',
						description: 'Calculate VAT amount',
						action: 'Calculate VAT amount',
					},
					{
						name: 'Calculate Margin',
						value: 'margin',
						description: 'Calculate profit margin',
						action: 'Calculate profit margin',
					},
					{
						name: 'Calculate Penalty',
						value: 'penalty',
						description: 'Calculate penalty amount',
						action: 'Calculate penalty amount',
					},
				],
				default: 'margin',
			},
			// VAT parameters
			{
				displayName: 'Amount',
				name: 'amount',
				type: 'number',
				required: true,
				displayOptions: {
					show: {
						operation: ['vat'],
					},
				},
				default: 0,
				description: 'Base amount for VAT calculation',
			},
			{
				displayName: 'VAT Rate (%)',
				name: 'vatRate',
				type: 'number',
				displayOptions: {
					show: {
						operation: ['vat'],
					},
				},
				default: 12,
				description: 'VAT rate in percentage (default 12% for Kazakhstan)',
			},
			// Margin parameters
			{
				displayName: 'Purchase Price',
				name: 'purchasePrice',
				type: 'number',
				required: true,
				displayOptions: {
					show: {
						operation: ['margin'],
					},
				},
				default: 0,
				description: 'Purchase price of goods/services',
			},
			{
				displayName: 'Sale Price',
				name: 'salePrice',
				type: 'number',
				required: true,
				displayOptions: {
					show: {
						operation: ['margin'],
					},
				},
				default: 0,
				description: 'Sale price of goods/services',
			},
			{
				displayName: 'Logistics Cost',
				name: 'logisticsCost',
				type: 'number',
				displayOptions: {
					show: {
						operation: ['margin'],
					},
				},
				default: 0,
				description: 'Additional logistics costs',
			},
			{
				displayName: 'Other Costs',
				name: 'otherCosts',
				type: 'number',
				displayOptions: {
					show: {
						operation: ['margin'],
					},
				},
				default: 0,
				description: 'Other additional costs',
			},
			// Penalty parameters
			{
				displayName: 'Contract Amount',
				name: 'contractAmount',
				type: 'number',
				required: true,
				displayOptions: {
					show: {
						operation: ['penalty'],
					},
				},
				default: 0,
				description: 'Total contract amount',
			},
			{
				displayName: 'Days Late',
				name: 'daysLate',
				type: 'number',
				required: true,
				displayOptions: {
					show: {
						operation: ['penalty'],
					},
				},
				default: 0,
				description: 'Number of days late',
			},
			{
				displayName: 'Penalty Rate (% per day)',
				name: 'penaltyRate',
				type: 'number',
				displayOptions: {
					show: {
						operation: ['penalty'],
					},
				},
				default: 0.1,
				description: 'Penalty rate per day in percentage',
			},
			// Advanced options
			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				options: [
					{
						displayName: 'Lot ID',
						name: 'lotId',
						type: 'number',
						default: 0,
						description: 'Lot identifier for tracking',
					},
					{
						displayName: 'Currency',
						name: 'currency',
						type: 'options',
						options: [
							{
								name: 'KZT (Kazakhstani Tenge)',
								value: 'KZT',
							},
							{
								name: 'USD (US Dollar)',
								value: 'USD',
							},
							{
								name: 'EUR (Euro)',
								value: 'EUR',
							},
							{
								name: 'RUB (Russian Ruble)',
								value: 'RUB',
							},
						],
						default: 'KZT',
						description: 'Currency for calculations',
					},
					{
						displayName: 'Save to Database',
						name: 'saveToDb',
						type: 'boolean',
						default: true,
						description: 'Whether to save calculation results to database',
					},
				],
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const operation = this.getNodeParameter('operation', 0) as string;

		for (let i = 0; i < items.length; i++) {
			try {
				let responseData;

				if (operation === 'vat') {
					responseData = await this.calculateVAT(i);
				} else if (operation === 'margin') {
					responseData = await this.calculateMargin(i);
				} else if (operation === 'penalty') {
					responseData = await this.calculatePenalty(i);
				}

				returnData.push({
					json: {
						operation,
						...responseData,
						timestamp: new Date().toISOString(),
					},
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: {
							error: error.message,
							operation,
						},
					});
					continue;
				}
				throw error;
			}
		}

		return [returnData];
	}

	private async calculateVAT(itemIndex: number): Promise<any> {
		const amount = this.getNodeParameter('amount', itemIndex) as number;
		const vatRate = this.getNodeParameter('vatRate', itemIndex, 12) as number;
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const requestBody = {
			amount,
			vat_rate: vatRate,
			currency: additionalFields.currency || 'KZT',
		};

		const options: OptionsWithUri = {
			method: 'POST',
			uri: 'http://localhost:8080/calc/vat',
			headers: {
				'Content-Type': 'application/json',
				'Accept': 'application/json',
			},
			body: requestBody,
			json: true,
		};

		try {
			const response = await this.helpers.request(options);

			// Save to database if requested
			if (additionalFields.saveToDb && additionalFields.lotId) {
				await this.saveCalculation('vat', additionalFields.lotId, requestBody, response);
			}

			return {
				input: requestBody,
				result: response,
				calculation_type: 'vat',
			};
		} catch (error) {
			throw new NodeOperationError(
				this.getNode(),
				`VAT calculation failed: ${error.message}`,
			);
		}
	}

	private async calculateMargin(itemIndex: number): Promise<any> {
		const purchasePrice = this.getNodeParameter('purchasePrice', itemIndex) as number;
		const salePrice = this.getNodeParameter('salePrice', itemIndex) as number;
		const logisticsCost = this.getNodeParameter('logisticsCost', itemIndex, 0) as number;
		const otherCosts = this.getNodeParameter('otherCosts', itemIndex, 0) as number;
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const requestBody = {
			purchase_price: purchasePrice,
			sale_price: salePrice,
			logistics_cost: logisticsCost,
			other_costs: otherCosts,
			currency: additionalFields.currency || 'KZT',
		};

		const options: OptionsWithUri = {
			method: 'POST',
			uri: 'http://localhost:8080/calc/margin',
			headers: {
				'Content-Type': 'application/json',
				'Accept': 'application/json',
			},
			body: requestBody,
			json: true,
		};

		try {
			const response = await this.helpers.request(options);

			// Save to database if requested
			if (additionalFields.saveToDb && additionalFields.lotId) {
				await this.saveCalculation('margin', additionalFields.lotId, requestBody, response);
			}

			return {
				input: requestBody,
				result: response,
				calculation_type: 'margin',
				profitability: response.margin_percent > 0 ? 'profitable' : 'unprofitable',
			};
		} catch (error) {
			throw new NodeOperationError(
				this.getNode(),
				`Margin calculation failed: ${error.message}`,
			);
		}
	}

	private async calculatePenalty(itemIndex: number): Promise<any> {
		const contractAmount = this.getNodeParameter('contractAmount', itemIndex) as number;
		const daysLate = this.getNodeParameter('daysLate', itemIndex) as number;
		const penaltyRate = this.getNodeParameter('penaltyRate', itemIndex, 0.1) as number;
		const additionalFields = this.getNodeParameter('additionalFields', itemIndex) as any;

		const requestBody = {
			contract_amount: contractAmount,
			days_late: daysLate,
			penalty_rate: penaltyRate,
			currency: additionalFields.currency || 'KZT',
		};

		const options: OptionsWithUri = {
			method: 'POST',
			uri: 'http://localhost:8080/calc/penalty',
			headers: {
				'Content-Type': 'application/json',
				'Accept': 'application/json',
			},
			body: requestBody,
			json: true,
		};

		try {
			const response = await this.helpers.request(options);

			// Save to database if requested
			if (additionalFields.saveToDb && additionalFields.lotId) {
				await this.saveCalculation('penalty', additionalFields.lotId, requestBody, response);
			}

			return {
				input: requestBody,
				result: response,
				calculation_type: 'penalty',
				severity: response.penalty_amount > contractAmount * 0.1 ? 'high' : 'low',
			};
		} catch (error) {
			throw new NodeOperationError(
				this.getNode(),
				`Penalty calculation failed: ${error.message}`,
			);
		}
	}

	private async saveCalculation(
		type: string,
		lotId: number,
		input: any,
		result: any
	): Promise<void> {
		// Optional: save calculation to database for audit trail
		try {
			const auditData = {
				calculation_type: type,
				lot_id: lotId,
				input_data: input,
				result_data: result,
				timestamp: new Date().toISOString(),
			};

			// This would typically call a separate audit endpoint
			// For now, we just log it
			console.log('Calculation audit:', JSON.stringify(auditData));
		} catch (error) {
			// Don't fail the main operation if audit fails
			console.error('Failed to save calculation audit:', error.message);
		}
	}
}
