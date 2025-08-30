# Flowise Tools for Zakupai

Custom Flowise tools for the Zakupai tender analysis platform. These tools provide integration between Flowise AI workflows and Zakupai services.

## Available Tools

### 1. Lot Reader (`lot-reader.json`)

- **Purpose**: Read and parse tender lot information from various sources
- **Sources**: Goszakup API, Internal Database, Zakupai Cache
- **Features**:
  - Multi-language support (ru, kz, en)
  - Automatic data enrichment with pricing and risk data
  - Formatted summaries

### 2. Risk Explain (`risk-explain.json`)

- **Purpose**: Explain risk factors and scores for tender lots
- **Features**:
  - Detailed risk analysis with multiple detail levels
  - Multi-format output (text, markdown, HTML, JSON)
  - Historical risk pattern analysis
  - Actionable risk mitigation recommendations
  - Multi-language explanations

### 3. Finance Calculator (`finance-calc.json`)

- **Purpose**: Financial calculations and analysis for tender lots
- **Calculations**:
  - VAT calculations (Kazakhstan 12% default)
  - Margin analysis and profitability
  - Penalty assessments
  - Full financial reports
- **Features**:
  - Multi-currency support (KZT, USD, EUR)
  - Automatic lot data integration
  - Financial recommendations

### 4. Template Generator (`template-gen.json`)

- **Purpose**: Generate documents from templates with dynamic data
- **Templates**:
  - TL;DR summaries
  - Guarantee letters
  - Business proposals
  - Risk reports
  - Financial analyses
  - Custom templates
- **Output Formats**: HTML, Markdown, Plain Text, PDF
- **Features**:
  - Auto-fetch lot data
  - Multi-language support
  - PDF generation via Zakupai doc-service

## Installation

### Prerequisites

- Flowise AI platform
- Access to Zakupai services
- Node.js environment

### Environment Variables

Configure these environment variables for the tools to work properly:

```bash
ZAKUPAI_BASE_URL=http://localhost:8000  # Base URL for Zakupai services
ZAKUPAI_API_KEY=your-api-key-here       # API key for authentication
```

### Installing Tools in Flowise

1. **Access Flowise Admin Panel**

1. **Navigate to Tools Section**

1. **Upload Tool Files**

   - Upload each `.json` file as a custom tool
   - Or paste the tool configuration directly

1. **Configure Tool Settings**

   - Verify environment variables are accessible
   - Test connections to Zakupai services

## Usage Examples

### Lot Analysis Workflow

```
1. Lot Reader → Extract lot data
2. Risk Explain → Analyze risks
3. Finance Calculator → Calculate margins
4. Template Generator → Create summary report
```

### Document Generation Workflow

```
1. Lot Reader → Get lot details
2. Template Generator (guarantee_letter) → Generate guarantee letter
3. Output as PDF for client delivery
```

### Risk Assessment Workflow

```
1. Lot Reader → Load lot with risk data
2. Risk Explain (detailed) → Full risk analysis
3. Template Generator (risk_report) → Format as report
```

## Tool Configuration

### Common Parameters

- **Language**: `ru` (Russian), `kz` (Kazakh), `en` (English)
- **Output Formats**: `text`, `markdown`, `html`, `json`, `pdf`
- **Currency**: `KZT` (Tenge), `USD`, `EUR`

### Authentication

All tools use the Zakupai API key for authentication. Ensure the `ZAKUPAI_API_KEY` environment variable is set.

### Error Handling

- Tools gracefully handle API failures
- Fallback data provided when services unavailable
- Detailed error messages for debugging

## Development

### Adding New Tools

1. Create new `.json` file with tool definition
1. Follow the existing structure and patterns
1. Include proper error handling and validation
1. Add multi-language support where applicable
1. Test with various input scenarios

### Tool Structure

```json
{
    "name": "Tool Name",
    "version": "1.0.0",
    "description": "Tool description",
    "icon": "🔧",
    "category": "Category",
    "type": "tool",
    "inputs": [...],
    "outputs": [...],
    "code": "..."
}
```

### Best Practices

- Use TypeScript-style code in tool definitions
- Include proper error handling and logging
- Support multiple languages where user-facing
- Provide meaningful default values
- Document all parameters clearly

## API Integration

### Zakupai Services

- **calc-service**: Financial calculations
- **risk-engine**: Risk assessment and scoring
- **doc-service**: Document generation and templates
- **embedding-api**: Search and similarity

### Goszakup Integration

- Direct API access for official tender data
- Automatic data synchronization
- Real-time updates support

## Troubleshooting

### Common Issues

1. **API Connection Errors**

   - Verify `ZAKUPAI_BASE_URL` is correct
   - Check API key validity
   - Ensure services are running

1. **Template Generation Failures**

   - Check template syntax for custom templates
   - Verify required data is available
   - Test with minimal data set first

1. **PDF Generation Issues**

   - Ensure doc-service is accessible
   - Check PDF options format
   - Fallback to HTML if PDF fails

1. **Localization Problems**

   - Verify language code format (ru, kz, en)
   - Check if translations exist for requested language
   - Fallback to default language (ru)

### Debug Mode

Set log level to debug for detailed information:

```bash
LOG_LEVEL=DEBUG
```

## Support

For issues and feature requests, please refer to the main Zakupai project documentation or create an issue in the project repository.

## Version History

- **1.0.0**: Initial release with 4 core tools
- Multi-language support
- PDF generation capabilities
- Full Zakupai API integration
