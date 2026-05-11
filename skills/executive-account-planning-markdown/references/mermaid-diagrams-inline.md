### PHASE 7.5: Mermaid Diagram Generation (OPTIONAL)

**PURPOSE**: Generate architecture diagrams, org charts, and timelines using Mermaid for embedding in the Markdown document.

**Workflow**:
1. Create Mermaid code blocks directly in Markdown (renders in GitHub, VS Code, etc.)
2. Alternatively, create temporary HTML file with Mermaid diagram code for PNG export
3. Open in browser to render the diagram
4. Use PNG export button to download diagram as image if needed
5. Delete temporary HTML file (optional)

#### Step 7.5.1: HTML Template for Diagram Generation

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ACCOUNT_NAME} - {PLANNING_FY} Account Plan</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({ 
            startOnLoad: true,
            theme: 'base',
            themeVariables: {
                primaryColor: '#E3F2FD',
                primaryBorderColor: '#29B5E8',
                secondaryColor: '#FFF8E1',
                tertiaryColor: '#E8F5E9',
                lineColor: '#666666',
                fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif'
            }
        });
    </script>
</head>
<body>
    <!-- Content sections -->
</body>
</html>
```

#### Step 7.5.2: Required Mermaid Diagrams

Generate these diagrams based on collected data:

**1. Current State Architecture** (from TECH_STACK, PARTNER_CONNECTIONS_VIEW)
```html
<div class="diagram-container" id="current-state">
    <pre class="mermaid">
graph LR
    subgraph Sources["Data Sources"]
        {TECH_STACK_SOURCES}
    end
    subgraph Integration["Data Integration"]
        {PARTNER_INTEGRATIONS}
    end
    subgraph Platform["Snowflake Platform"]
        dw[(Data Warehouse)]
        {ADOPTED_FEATURES}
    end
    subgraph Consumption["Consumption"]
        {BI_TOOLS}
    end
    {CONNECTION_ARROWS}
    </pre>
</div>
```

**2. Future State Architecture** (incorporating white space opportunities)
```html
<div class="diagram-container" id="future-state">
    <pre class="mermaid">
graph LR
    subgraph Expanded["Expanded Platform"]
        {CURRENT_FEATURES}
        {WHITE_SPACE_FEATURES}
    end
    </pre>
</div>
```

**3. Stakeholder Org Chart** (from LinkedIn research, Snow Owl)
```html
<div class="diagram-container" id="org-chart">
    <pre class="mermaid">
graph TD
    {STAKEHOLDER_HIERARCHY}
    
    style champion fill:#29B5E8,color:#fff
    style economic_buyer fill:#10B981,color:#fff
    style technical_buyer fill:#F59E0B,color:#fff
    </pre>
</div>
```

**4. Use Case Timeline** (from SDA_USE_CASE_VIEW)
```html
<div class="diagram-container" id="timeline">
    <pre class="mermaid">
gantt
    title Use Case Pipeline - {PLANNING_FY}
    dateFormat YYYY-MM
    section Production
    {PRODUCTION_USE_CASES}
    section In Progress
    {ACTIVE_USE_CASES}
    section Planned
    {PLANNED_USE_CASES}
    </pre>
</div>
```

**5. Partner Ecosystem** (from PARTNER_CONNECTIONS_VIEW)
```html
<div class="diagram-container" id="partners">
    <pre class="mermaid">
graph TB
    sf((Snowflake))
    {PARTNER_NODES}
    {PARTNER_CONNECTIONS}
    style sf fill:#29B5E8,color:#fff
    </pre>
</div>
```

#### Step 7.5.3: PNG Export Script

Include this JavaScript for diagram export:

```javascript
async function downloadPng(containerId, filename) {
    const container = document.getElementById(containerId);
    const svg = container.querySelector('svg');
    if (!svg) {
        alert('Diagram not found');
        return;
    }
    
    const svgData = new XMLSerializer().serializeToString(svg);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);
    
    const img = new Image();
    img.onload = function() {
        const canvas = document.createElement('canvas');
        const scale = 2;
        canvas.width = img.width * scale;
        canvas.height = img.height * scale;
        
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.scale(scale, scale);
        ctx.drawImage(img, 0, 0);
        
        canvas.toBlob(function(blob) {
            const pngUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = pngUrl;
            link.download = filename + '.png';
            link.click();
            URL.revokeObjectURL(pngUrl);
        }, 'image/png');
        
        URL.revokeObjectURL(url);
    };
    img.src = url;
}
```

#### Step 7.5.4: Save HTML and Open in Browser

```python
# Generate filename
safe_name = ACCOUNT_NAME.replace(' ', '_').replace('+', '').replace('&', 'and')
safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')
html_filename = f"{safe_name}_{PLANNING_FY}_Account_Plan_{datetime.now().strftime('%Y%m%d')}.html"
html_output_path = os.path.join(OUTPUT_DIR, html_filename)

# Write HTML file
with open(html_output_path, 'w') as f:
    f.write(html_content)

# Open in browser
import webbrowser
webbrowser.open(f'file://{html_output_path}')

print(f"HTML report saved and opened: {html_output_path}")
```

---

