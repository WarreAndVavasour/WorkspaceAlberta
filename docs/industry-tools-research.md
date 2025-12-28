# Industry Tools Research: Lumber, Aluminum & Steel

Research compiled for building MCP tool integrations for custom IDEs.

---

## Table of Contents

1. [Lumber Industry](#lumber-industry)
2. [Aluminum Industry](#aluminum-industry)
3. [Steel Industry](#steel-industry)
4. [Cross-Industry Tools](#cross-industry-tools)
5. [Recommended MCP Catalog Additions](#recommended-mcp-catalog-additions)

---

## Lumber Industry

### ERP Systems

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **TimberERP** | Full sawmill ERP with API/EDI support | `proxy` | API + EDI integration with external systems |
| **Epicor LumberTrack** | Log procurement, production planning, inventory | `proxy` | Includes FiberTrack for log tracking |
| **WoodPro InSight** | Sawmill/LBM dealer management | `proxy` | Integrates with Tableau, Qlik, Power BI |
| **Timber by Pinja** | Modular MES/ERP for sawmills | `proxy` | SAP/M365 integration capable |
| **TiCom (TimberTec)** | Timber industry ERP | `proxy` | 25+ years in timber software |

### Log Scaling & Measurement

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **Tally-I/O** | Log tally, scaling, grading software | `proxy` | Multiple log rules (Doyle, Scribner, etc.) |
| **3LOG LIMS** | Log inventory management system | `proxy` | Electronic capture from measuring instruments |
| **Trimble LIMS** | Enterprise forestry management | `proxy` | 500+ forestry enterprises |
| **Forestry Systems Logscaler** | Log operation scaling | `proxy` | User-friendly scaling program |

### Cut Optimization

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **CutLog** | Sawmill optimization software | `proxy` | Pattern optimization for log sawing |
| **Pitago** | Log-to-timber cutting optimizer | `proxy` | Claims 7-12% yield improvement |
| **Opti-Sawmill** | Production planning & yield | `proxy` | Calculates optimal log diameter sorting |
| **ROMI-RIP (USDA)** | Lumber cut-up simulation | `proxy` | Research-grade optimizer |

### Pricing & Market Data

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **Commodities-API (Lumber)** | Real-time lumber futures | `openapi` | REST API available |
| **Random Lengths (Fastmarkets)** | Industry-standard lumber pricing | `proxy` | 1,600+ price items, subscription required |
| **ResourceWise** | Forest products commodity pricing | `proxy` | Stumpage 360 database |

### Certification & Chain of Custody

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **FSC Chain of Custody** | Forest certification tracking | `proxy` | Gold standard certification |
| **PEFC Chain of Custody** | Sustainable forestry certification | `proxy` | International standard |

---

## Aluminum Industry

### ERP Systems

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **Lighthouse ERP (Aluminum)** | Extrusion-focused ERP | `proxy` | Die management, production planning |
| **JOBSCOPE** | Aluminum fabrication ERP | `proxy` | 45+ years, time-phased materials |
| **Sage X3** | Metal sheets manufacturing | `proxy` | Scrap/offcut management |
| **Focus Softnet** | Cloud-based manufacturing ERP | `proxy` | ASTM/ISO compliance |

### Extrusion-Specific

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **KmExtrusion (META 2i)** | MES for aluminum extrusion | `proxy` | Die management, ERP linking |
| **Atieuno EMS** | Extrusion management system | `proxy` | Theoria planning module |
| **ExtrusionPower** | CAD/CAM/Simulation for dies | `proxy` | Die design and simulation |
| **Extrusion ERP (ITPlusPoint)** | Multi-industry extrusion ERP | `proxy` | Aluminum, plastic, food extrusion |

### Inventory & Fabrication

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **xTuple** | Open-source metal fabrication ERP | `openapi` | 20+ years in metal fabrication |
| **MRPeasy** | SMB manufacturing ERP | `proxy` | Up to 200 employees |
| **Metal-Pro** | Metal processing inventory | `proxy` | Flexible inventory management |

---

## Steel Industry

### ERP & Service Center Software

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **RealSTEEL** | MS Dynamics 365-based steel ERP | `proxy` | Coil processing, shop floor capture |
| **PSData Steel Software** | Steel ERP with REST API | `openapi` | **Explicit Steel API** for integration |
| **INVEX (Invera)** | Metal service center ERP | `proxy` | eCommerce platform included |
| **Jonas Metals** | Service center ERP | `proxy` | Slitting to cut-to-length |
| **Crowe Metals Accelerator** | MS Dynamics 365 metals solution | `proxy` | Coil slitting optimization |
| **MetalTrax** | Affordable metal/steel software | `proxy` | Service centers, distributors |
| **Eniteo (Enmark)** | #1 rated metals ERP | `proxy` | Purpose-built for service centers |
| **Steel Manager III** | Comprehensive metal ERP | `proxy` | Modern Windows interface |
| **TSS Software Steel ERP** | Heat/coil tracking | `proxy` | Coil weight, grade, location |

### Coil/Sheet Processing & Optimization

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **CCO (Fast-Square)** | Coil cut optimizer | `proxy` | Slitting pattern optimization |
| **CutLogic 1D/2D** | Nesting and cut optimization | `proxy` | ActiveX engine for integration |
| **AutoBarSizer (Fraunhofer)** | Steel profile cutting | `proxy` | **XML API interface** |
| **FastCUT Optimizer** | Rectangular/linear nesting | `proxy` | Coil cut-to-length support |
| **1D-Solutions** | Linear cutting DLL | `proxy` | **DLL for integration** |

### Traceability & Quality

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **MetalTrace (MTR)** | Mill Test Report management | `proxy` | Heat number tracking, ERP integration |
| **Certivo** | AI-powered MTR analysis | `proxy` | Automated compliance checking |
| **Data Functions MTR** | Heat number software | `proxy` | Pipe, valves, fittings focus |

---

## Cross-Industry Tools

### Metal Pricing APIs

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **Metals-API** | LME pricing data | `openapi` | **REST API**, gold/silver/base metals |
| **LME Direct** | Official LME data | `proxy` | Real-time and historical |
| **LSEG (Refinitiv)** | LME data feed | `proxy` | Low-latency trading data |
| **Fastmarkets Dashboard** | LME/CME/SHFE pricing | `proxy` | Physical and exchange prices |
| **Commodities-API** | Multiple commodities | `openapi` | **REST API**, 60-second updates |

### Industrial Weighing & Scale Integration

| Tool | Description | Integration Status | Notes |
|------|-------------|-------------------|-------|
| **Waybiller** | Truck scale integration | `proxy` | Multi-brand scale API |
| **mScales** | Scale management platform | `openapi` | **HTTPS REST API** |
| **Arlyn AxChange** | Scale data monitoring | `openapi` | **REST API**, CSV/Excel export |
| **METTLER TOLEDO** | Industrial weighing systems | `proxy` | Full process control |
| **Precision Solutions** | Custom weighing integration | `proxy` | PLC/ERP integration |

---

## Recommended MCP Catalog Additions

### Priority 1: APIs with Documented REST/OpenAPI Support

```json
[
  {
    "id": "metals_api",
    "display_name": "Metals-API (LME)",
    "category": "Industrial / Metals",
    "description": "LME base metals and precious metals pricing",
    "integration_status": "openapi",
    "mcp": {
      "server_name": "metals-api",
      "type": "http_openapi",
      "openapi_url": "https://metals-api.com/documentation",
      "env_vars": [
        { "name": "METALS_API_KEY", "description": "API access key" }
      ]
    }
  },
  {
    "id": "commodities_api_lumber",
    "display_name": "Commodities-API (Lumber)",
    "category": "Industrial / Lumber",
    "description": "Real-time lumber futures and commodity pricing",
    "integration_status": "openapi",
    "mcp": {
      "server_name": "commodities-api",
      "type": "http_openapi",
      "openapi_url": "https://commodities-api.com/documentation",
      "env_vars": [
        { "name": "COMMODITIES_API_KEY", "description": "API access key" }
      ]
    }
  },
  {
    "id": "psdata_steel_api",
    "display_name": "PSData Steel API",
    "category": "Industrial / Steel",
    "description": "Steel ERP integration - inventory, orders, data sync",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "psdata-steel",
      "type": "http_openapi",
      "openapi_url_env": "PSDATA_STEEL_OPENAPI_URL",
      "env_vars": [
        { "name": "PSDATA_STEEL_API_KEY", "description": "Steel API access key" },
        { "name": "PSDATA_STEEL_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "mscales",
    "display_name": "mScales",
    "category": "Industrial / Weighing",
    "description": "Industrial scale integration platform",
    "integration_status": "openapi",
    "mcp": {
      "server_name": "mscales",
      "type": "http_openapi",
      "openapi_url": "https://www.mscales.com/api/spec",
      "env_vars": [
        { "name": "MSCALES_API_KEY", "description": "API authentication key" },
        { "name": "MSCALES_ACCOUNT_ID", "description": "Account identifier" }
      ]
    }
  },
  {
    "id": "arlyn_axchange",
    "display_name": "Arlyn AxChange",
    "category": "Industrial / Weighing",
    "description": "Scale weight monitoring and tracking REST API",
    "integration_status": "openapi",
    "mcp": {
      "server_name": "arlyn-axchange",
      "type": "http_openapi",
      "openapi_url_env": "ARLYN_OPENAPI_URL",
      "env_vars": [
        { "name": "ARLYN_API_KEY", "description": "AxChange API key" },
        { "name": "ARLYN_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  }
]
```

### Priority 2: ERP Systems Requiring Custom Wrappers

```json
[
  {
    "id": "timber_erp",
    "display_name": "TimberERP",
    "category": "Industrial / Lumber",
    "description": "Sawmill ERP - logs, timber, production",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "timber-erp",
      "type": "http_openapi",
      "openapi_url_env": "TIMBER_ERP_OPENAPI_URL",
      "env_vars": [
        { "name": "TIMBER_ERP_API_KEY", "description": "API access key" },
        { "name": "TIMBER_ERP_BASE_URL", "description": "Instance base URL" },
        { "name": "TIMBER_ERP_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "realsteel",
    "display_name": "RealSTEEL",
    "category": "Industrial / Steel",
    "description": "MS Dynamics 365-based steel/metals ERP",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "realsteel",
      "type": "http_openapi",
      "openapi_url_env": "REALSTEEL_OPENAPI_URL",
      "env_vars": [
        { "name": "REALSTEEL_CLIENT_ID", "description": "OAuth client ID" },
        { "name": "REALSTEEL_CLIENT_SECRET", "description": "OAuth client secret" },
        { "name": "REALSTEEL_TENANT_ID", "description": "Dynamics 365 tenant" },
        { "name": "REALSTEEL_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "metaltrace_mtr",
    "display_name": "MetalTrace MTR",
    "category": "Industrial / Steel",
    "description": "Mill Test Report and heat number tracking",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "metaltrace",
      "type": "http_openapi",
      "openapi_url_env": "METALTRACE_OPENAPI_URL",
      "env_vars": [
        { "name": "METALTRACE_API_KEY", "description": "API access key" },
        { "name": "METALTRACE_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "lighthouse_aluminum",
    "display_name": "Lighthouse ERP (Aluminum)",
    "category": "Industrial / Aluminum",
    "description": "Aluminum extrusion ERP - die management, production",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "lighthouse-aluminum",
      "type": "http_openapi",
      "openapi_url_env": "LIGHTHOUSE_OPENAPI_URL",
      "env_vars": [
        { "name": "LIGHTHOUSE_API_KEY", "description": "API access key" },
        { "name": "LIGHTHOUSE_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "kmextrusion",
    "display_name": "KmExtrusion MES",
    "category": "Industrial / Aluminum",
    "description": "MES for aluminum extrusion - die/tool management",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "kmextrusion",
      "type": "http_openapi",
      "openapi_url_env": "KMEXTRUSION_OPENAPI_URL",
      "env_vars": [
        { "name": "KMEXTRUSION_API_KEY", "description": "API access key" },
        { "name": "KMEXTRUSION_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "tally_io",
    "display_name": "Tally-I/O",
    "category": "Industrial / Lumber",
    "description": "Log tally, scaling, and sawmill inventory",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "tally-io",
      "type": "http_openapi",
      "openapi_url_env": "TALLYIO_OPENAPI_URL",
      "env_vars": [
        { "name": "TALLYIO_API_KEY", "description": "API access key" },
        { "name": "TALLYIO_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  }
]
```

### Priority 3: Cut Optimization & Specialized Tools

```json
[
  {
    "id": "cutlog",
    "display_name": "CutLog",
    "category": "Industrial / Lumber",
    "description": "Sawmill cutting pattern optimization",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "cutlog",
      "type": "http_openapi",
      "openapi_url_env": "CUTLOG_OPENAPI_URL",
      "env_vars": [
        { "name": "CUTLOG_LICENSE_KEY", "description": "Software license" },
        { "name": "CUTLOG_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "fast_square_cco",
    "display_name": "Fast-Square CCO",
    "category": "Industrial / Steel",
    "description": "Coil cut optimizer for steel slitting",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "fast-square-cco",
      "type": "http_openapi",
      "openapi_url_env": "FASTSQUARE_OPENAPI_URL",
      "env_vars": [
        { "name": "FASTSQUARE_LICENSE_KEY", "description": "License key" },
        { "name": "FASTSQUARE_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "autobarsizer",
    "display_name": "AutoBarSizer",
    "category": "Industrial / Steel",
    "description": "Steel profile cutting optimization (XML API)",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "autobarsizer",
      "type": "http_openapi",
      "openapi_url_env": "AUTOBARSIZER_OPENAPI_URL",
      "env_vars": [
        { "name": "AUTOBARSIZER_LICENSE", "description": "Software license" },
        { "name": "AUTOBARSIZER_OPENAPI_URL", "description": "OpenAPI wrapper URL" }
      ]
    }
  },
  {
    "id": "waybiller",
    "display_name": "Waybiller",
    "category": "Industrial / Weighing",
    "description": "Truck scale integration platform",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "waybiller",
      "type": "http_openapi",
      "openapi_url_env": "WAYBILLER_OPENAPI_URL",
      "env_vars": [
        { "name": "WAYBILLER_API_KEY", "description": "API access key" },
        { "name": "WAYBILLER_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  },
  {
    "id": "trimble_lims",
    "display_name": "Trimble LIMS",
    "category": "Industrial / Lumber",
    "description": "Log Inventory Management System",
    "integration_status": "proxy",
    "mcp": {
      "server_name": "trimble-lims",
      "type": "http_openapi",
      "openapi_url_env": "TRIMBLE_LIMS_OPENAPI_URL",
      "env_vars": [
        { "name": "TRIMBLE_LIMS_API_KEY", "description": "API key" },
        { "name": "TRIMBLE_LIMS_OPENAPI_URL", "description": "OpenAPI spec URL" }
      ]
    }
  }
]
```

---

## Key Observations

### APIs with Best Integration Potential

1. **Metals-API / Commodities-API** - Public REST APIs with documentation
2. **PSData Steel API** - Explicitly designed for integration
3. **mScales / Arlyn AxChange** - Modern REST APIs for scale integration
4. **AutoBarSizer** - XML interface for embedding in applications

### Integration Challenges

1. **Most ERP systems** require custom OpenAPI wrappers
2. **Pricing data** (Random Lengths, LME) often subscription-based
3. **Legacy systems** may only support file-based or EDI integration
4. **On-premise software** may need local proxy servers

### Industry Trends (2025)

- Cloud-based ERP adoption accelerating
- AI/ML integration for predictive maintenance and optimization
- Real-time data synchronization becoming standard
- Mobile access increasingly important

---

## Sources

### Lumber Industry
- [WoodPro Software](https://www.woodprosoftware.com/)
- [TimberERP](https://www.timbererp.com/)
- [Epicor LumberTrack](https://www.epicor.com/en-us/products/enterprise-resource-planning-erp/lumbertrack/)
- [Pinja Timber](https://pinja.com/services/forest-industry/timber)
- [TimberTec TiCom](https://timbertec.com/en/)
- [Tally-I/O](https://tally-io.com/)
- [CutLog](https://www.cutlog.com/)
- [Trimble Forestry](https://forestry.trimble.com/)
- [Commodities-API Lumber](https://commodities-api.com/symbols/LUMBER)
- [Fastmarkets Random Lengths](https://www.fastmarkets.com/forest-products/random-lengths-weekly-report/)

### Aluminum Industry
- [Lighthouse ERP](https://www.lighthouseindia.com/Aluminum-Extrusion-Profiles-erp.html)
- [KmExtrusion](https://kmextrusion.com/en/)
- [Atieuno EMS](https://www.atieuno.com/aluminium-extrusion-software/)
- [ExtrusionPower](https://www.extrusionpower.com/)
- [JOBSCOPE](https://www.jobscope.com/metal-steel-fabrication.html)
- [Sage X3 for Aluminum](https://www.sagesoftware.co.in/erp-software-for-aluminium-metal-sheets/)

### Steel Industry
- [RealSTEEL Software](https://www.realsteelsoftware.com/)
- [PSData Steel Software](https://www.mysteelsoftware.com/)
- [INVEX by Invera](https://invera.com/invex/)
- [Jonas Metals](https://www.jonasmetals.com/)
- [Crowe Metals](https://www.crowe.com/services/consulting/metals/)
- [MetalTrace MTR](https://www.traceapps.com/)
- [Fast-Square CCO](https://www.fast-square.net/)
- [AutoBarSizer](https://www.scapos.com/products/nesting-packing/autobarsizer-cutting-optimization-software.html)

### Metal Pricing
- [Metals-API](https://metals-api.com)
- [LME Market Data](https://www.lme.com/Market-data)
- [LSEG LME Data](https://www.lseg.com/en/data-analytics/financial-data/commodities-data/lme-data)

### Weighing Systems
- [mScales API](https://www.mscales.com/documents/mscales-api-connection)
- [Arlyn AxChange](https://www.arlynscales.com/axchange-monitoring/)
- [Waybiller](https://waybiller.com/truck-scale/)
