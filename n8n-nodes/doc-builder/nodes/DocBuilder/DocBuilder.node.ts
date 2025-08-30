import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

export class DocBuilder implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Doc Builder',
		name: 'docBuilder',
		icon: 'file:doc-builder.svg',
		group: ['output'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Generate documents from templates and data',
		defaults: {
			name: 'Doc Builder',
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
						name: 'Create TL;DR',
						value: 'createTldr',
						description: 'Create TL;DR summary of a lot',
						action: 'Create TL;DR summary',
					},
					{
						name: 'Generate Letter',
						value: 'generateLetter',
						description: 'Generate business letter from template',
						action: 'Generate letter',
					},
					{
						name: 'Render HTML',
						value: 'renderHtml',
						description: 'Render document as HTML',
						action: 'Render HTML',
					},
					{
						name: 'Render PDF',
						value: 'renderPdf',
						description: 'Render document as PDF',
						action: 'Render PDF',
					},
					{
						name: 'Get Templates',
						value: 'getTemplates',
						description: 'Get available document templates',
						action: 'Get templates',
					},
					{
						name: 'Create Template',
						value: 'createTemplate',
						description: 'Create new document template',
						action: 'Create template',
					},
					{
						name: 'Update Template',
						value: 'updateTemplate',
						description: 'Update existing document template',
						action: 'Update template',
					},
				],
				default: 'createTldr',
			},
			// Lot ID for TL;DR
			{
				displayName: 'Lot ID',
				name: 'lotId',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['createTldr'],
					},
				},
				default: '',
				description: 'ID of the lot to summarize',
			},
			// Template selection
			{
				displayName: 'Template',
				name: 'template',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['generateLetter', 'renderHtml', 'renderPdf'],
					},
				},
				default: '',
				description: 'Template name or ID to use',
			},
			// Template ID for updates
			{
				displayName: 'Template ID',
				name: 'templateId',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['updateTemplate'],
					},
				},
				default: '',
				description: 'ID of the template to update',
			},
			// Document data
			{
				displayName: 'Document Data',
				name: 'documentData',
				type: 'json',
				displayOptions: {
					show: {
						operation: ['generateLetter', 'renderHtml', 'renderPdf'],
					},
				},
				default: '{}',
				description: 'Data to merge with template (JSON format)',
			},
			// Template content for creation/update
			{
				displayName: 'Template Content',
				name: 'templateContent',
				type: 'string',
				typeOptions: {
					alwaysOpenEditWindow: true,
					rows: 10,
				},
				displayOptions: {
					show: {
						operation: ['createTemplate', 'updateTemplate'],
					},
				},
				default: '',
				description: 'Template content (HTML/Markdown)',
			},
			// Template metadata
			{
				displayName: 'Template Name',
				name: 'templateName',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						operation: ['createTemplate'],
					},
				},
				default: '',
				description: 'Name of the new template',
			},
			{
				displayName: 'Template Description',
				name: 'templateDescription',
				type: 'string',
				displayOptions: {
					show: {
						operation: ['createTemplate', 'updateTemplate'],
					},
				},
				default: '',
				description: 'Description of the template',
			},
			// Document options
			{
				displayName: 'Document Options',
				name: 'documentOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: {
					show: {
						operation: ['createTldr', 'generateLetter', 'renderHtml', 'renderPdf'],
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
						description: 'Document language',
					},
					{
						displayName: 'Format',
						name: 'format',
						type: 'options',
						options: [
							{
								name: 'HTML',
								value: 'html',
							},
							{
								name: 'Markdown',
								value: 'markdown',
							},
							{
								name: 'Plain Text',
								value: 'text',
							},
						],
						default: 'html',
						description: 'Output format',
					},
					{
						displayName: 'Include Metadata',
						name: 'includeMetadata',
						type: 'boolean',
						default: false,
						description: 'Include document metadata in response',
					},
				],
			},
			// PDF-specific options
			{
				displayName: 'PDF Options',
				name: 'pdfOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: {
					show: {
						operation: ['renderPdf'],
					},
				},
				options: [
					{
						displayName: 'Page Size',
						name: 'pageSize',
						type: 'options',
						options: [
							{
								name: 'A4',
								value: 'A4',
							},
							{
								name: 'A3',
								value: 'A3',
							},
							{
								name: 'Letter',
								value: 'Letter',
							},
						],
						default: 'A4',
						description: 'PDF page size',
					},
					{
						displayName: 'Orientation',
						name: 'orientation',
						type: 'options',
						options: [
							{
								name: 'Portrait',
								value: 'portrait',
							},
							{
								name: 'Landscape',
								value: 'landscape',
							},
						],
						default: 'portrait',
						description: 'PDF orientation',
					},
					{
						displayName: 'Margins',
						name: 'margins',
						type: 'string',
						default: '20mm',
						description: 'PDF margins (e.g., "20mm" or "1in")',
					},
				],
			},
			// Template filters
			{
				displayName: 'Template Filters',
				name: 'templateFilters',
				type: 'collection',
				placeholder: 'Add Filter',
				default: {},
				displayOptions: {
					show: {
						operation: ['getTemplates'],
					},
				},
				options: [
					{
						displayName: 'Category',
						name: 'category',
						type: 'string',
						default: '',
						description: 'Filter by template category',
					},
					{
						displayName: 'Tag',
						name: 'tag',
						type: 'string',
						default: '',
						description: 'Filter by template tag',
					},
					{
						displayName: 'Language',
						name: 'language',
						type: 'options',
						options: [
							{
								name: 'All',
								value: '',
							},
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
						default: '',
						description: 'Filter by language',
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
					case 'createTldr':
						responseData = await this.createTldr(i, credentials);
						break;
					case 'generateLetter':
						responseData = await this.generateLetter(i, credentials);
						break;
					case 'renderHtml':
						responseData = await this.renderHtml(i, credentials);
						break;
					case 'renderPdf':
						responseData = await this.renderPdf(i, credentials);
						break;
					case 'getTemplates':
						responseData = await this.getTemplates(i, credentials);
						break;
					case 'createTemplate':
						responseData = await this.createTemplate(i, credentials);
						break;
					case 'updateTemplate':
						responseData = await this.updateTemplate(i, credentials);
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
			throw new NodeOperationError(this.getNode(), `Doc Builder API request failed: ${error.message}`);
		}
	}

	private async createTldr(itemIndex: number, credentials: any): Promise<any> {
		const lotId = this.getNodeParameter('lotId', itemIndex) as string;
		const documentOptions = this.getNodeParameter('documentOptions', itemIndex) as any;

		const params: any = {};
		if (documentOptions.language) {
			params.lang = documentOptions.language;
		}
		if (documentOptions.format) {
			params.format = documentOptions.format;
		}
		if (documentOptions.includeMetadata) {
			params.include_metadata = documentOptions.includeMetadata;
		}

		const queryString = Object.keys(params).length > 0 ? '?' + new URLSearchParams(params).toString() : '';
		return this.makeRequest(`/tldr/${lotId}${queryString}`, credentials);
	}

	private async generateLetter(itemIndex: number, credentials: any): Promise<any> {
		const template = this.getNodeParameter('template', itemIndex) as string;
		const documentData = this.getNodeParameter('documentData', itemIndex) as string;
		const documentOptions = this.getNodeParameter('documentOptions', itemIndex) as any;

		const body: any = {
			template,
		};

		if (documentData && documentData !== '{}') {
			try {
				body.data = JSON.parse(documentData);
			} catch (error) {
				throw new NodeOperationError(this.getNode(), 'Invalid JSON in document data');
			}
		}

		if (documentOptions.language) {
			body.language = documentOptions.language;
		}
		if (documentOptions.format) {
			body.format = documentOptions.format;
		}

		return this.makeRequest('/letters/generate', credentials, 'POST', body);
	}

	private async renderHtml(itemIndex: number, credentials: any): Promise<any> {
		const template = this.getNodeParameter('template', itemIndex) as string;
		const documentData = this.getNodeParameter('documentData', itemIndex) as string;
		const documentOptions = this.getNodeParameter('documentOptions', itemIndex) as any;

		const body: any = {
			template,
		};

		if (documentData && documentData !== '{}') {
			try {
				body.data = JSON.parse(documentData);
			} catch (error) {
				throw new NodeOperationError(this.getNode(), 'Invalid JSON in document data');
			}
		}

		if (documentOptions.language) {
			body.language = documentOptions.language;
		}

		return this.makeRequest('/render/html', credentials, 'POST', body);
	}

	private async renderPdf(itemIndex: number, credentials: any): Promise<any> {
		const template = this.getNodeParameter('template', itemIndex) as string;
		const documentData = this.getNodeParameter('documentData', itemIndex) as string;
		const documentOptions = this.getNodeParameter('documentOptions', itemIndex) as any;
		const pdfOptions = this.getNodeParameter('pdfOptions', itemIndex) as any;

		const body: any = {
			template,
		};

		if (documentData && documentData !== '{}') {
			try {
				body.data = JSON.parse(documentData);
			} catch (error) {
				throw new NodeOperationError(this.getNode(), 'Invalid JSON in document data');
			}
		}

		if (documentOptions.language) {
			body.language = documentOptions.language;
		}

		if (pdfOptions.pageSize) {
			body.page_size = pdfOptions.pageSize;
		}
		if (pdfOptions.orientation) {
			body.orientation = pdfOptions.orientation;
		}
		if (pdfOptions.margins) {
			body.margins = pdfOptions.margins;
		}

		return this.makeRequest('/render/pdf', credentials, 'POST', body);
	}

	private async getTemplates(itemIndex: number, credentials: any): Promise<any> {
		const templateFilters = this.getNodeParameter('templateFilters', itemIndex) as any;

		const params: any = {};
		if (templateFilters.category) {
			params.category = templateFilters.category;
		}
		if (templateFilters.tag) {
			params.tag = templateFilters.tag;
		}
		if (templateFilters.language) {
			params.language = templateFilters.language;
		}

		const queryString = Object.keys(params).length > 0 ? '?' + new URLSearchParams(params).toString() : '';
		return this.makeRequest(`/templates${queryString}`, credentials);
	}

	private async createTemplate(itemIndex: number, credentials: any): Promise<any> {
		const templateName = this.getNodeParameter('templateName', itemIndex) as string;
		const templateContent = this.getNodeParameter('templateContent', itemIndex) as string;
		const templateDescription = this.getNodeParameter('templateDescription', itemIndex) as string;

		const body: any = {
			name: templateName,
			content: templateContent,
		};

		if (templateDescription) {
			body.description = templateDescription;
		}

		return this.makeRequest('/templates', credentials, 'POST', body);
	}

	private async updateTemplate(itemIndex: number, credentials: any): Promise<any> {
		const templateId = this.getNodeParameter('templateId', itemIndex) as string;
		const templateContent = this.getNodeParameter('templateContent', itemIndex) as string;
		const templateDescription = this.getNodeParameter('templateDescription', itemIndex) as string;

		const body: any = {
			content: templateContent,
		};

		if (templateDescription) {
			body.description = templateDescription;
		}

		return this.makeRequest(`/templates/${templateId}`, credentials, 'PUT', body);
	}
}
