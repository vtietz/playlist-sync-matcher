"""HTML report template generation with jQuery DataTables."""
from typing import Optional


def get_html_template(
    title: str, 
    columns: list[str], 
    rows: list[list], 
    description: str = "",
    default_order: Optional[list[list[int | str]]] = None
) -> str:
    """Generate a DataTables-powered HTML report with pagination and search.
    
    Args:
        title: Report title
        columns: List of column headers
        rows: List of row data (each row is a list of cell values)
        description: Optional description text shown above the table
        default_order: Default sort order as [[col_idx, 'asc'/'desc'], ...]. 
                      Example: [[0, 'desc'], [1, 'asc']] sorts by col 0 DESC, then col 1 ASC
    
    Returns:
        Complete HTML document as string
    """
    # Build table headers
    header_html = "".join(f'<th>{col}</th>' for col in columns)
    
    # Build table rows
    rows_html = []
    for row in rows:
        cells_html = "".join(f"<td>{cell if cell is not None else ''}</td>" for cell in row)
        rows_html.append(f"<tr>{cells_html}</tr>")
    
    table_body = "\n".join(rows_html)
    
    # Default order JSON
    if default_order:
        order_json = str(default_order).replace("'", '"')
    else:
        order_json = "[[0, 'asc']]"
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    
    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    
    <!-- DataTables CSS & JS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        html, body {{
            height: 100%;
            min-height: 100%;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: white;
            color: #333;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 30px;
        }}
        
        h1 {{
            color: #1a73e8;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        
        .description {{
            color: #666;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        
        /* Link styles */
        a {{
            color: #1a73e8;
            text-decoration: none;
            transition: color 0.2s ease;
        }}
        
        a:hover {{
            color: #1557b0;
            text-decoration: underline;
        }}
        
        /* DataTables styling overrides */
        #dataTable {{
            width: 100% !important;
        }}
        
        #dataTable thead th {{
            background: #1a73e8 !important;
            color: white !important;
            padding: 12px !important;
            font-weight: 600;
        }}
        
        #dataTable tbody td {{
            padding: 10px 12px;
        }}
        
        #dataTable tbody tr:hover {{
            background: #f8f9fa !important;
        }}
        
        .dataTables_wrapper .dataTables_length,
        .dataTables_wrapper .dataTables_filter,
        .dataTables_wrapper .dataTables_info,
        .dataTables_wrapper .dataTables_paginate {{
            margin-top: 10px;
            margin-bottom: 10px;
        }}
        
        .dataTables_wrapper .dataTables_filter input {{
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 5px 10px;
            margin-left: 5px;
        }}
        
        .dataTables_wrapper .dataTables_length select {{
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 5px;
            margin: 0 5px;
        }}
        
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
        
        /* Badge styles for confidence levels */
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .badge-certain {{
            background: #34a853;
            color: white;
        }}
        
        .badge-high {{
            background: #4285f4;
            color: white;
        }}
        
        .badge-medium {{
            background: #fbbc04;
            color: #333;
        }}
        
        .badge-low {{
            background: #ea4335;
            color: white;
        }}
        
        .badge-unknown {{
            background: #9e9e9e;
            color: white;
        }}
        
        /* Checkbox symbols */
        .check-yes {{
            color: #34a853;
            font-weight: bold;
            font-size: 16px;
        }}
        
        .check-no {{
            color: #ea4335;
            font-weight: bold;
            font-size: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        {f'<div class="description">{description}</div>' if description else ''}
        
        <table id="dataTable" class="display">
            <thead>
                <tr>{header_html}</tr>
            </thead>
            <tbody>
{table_body}
            </tbody>
        </table>
        
        <div class="footer">
            Generated by Playlist Sync Matcher • Powered by jQuery DataTables
        </div>
    </div>
    
    <script>
        $(document).ready(function() {{
            $('#dataTable').DataTable({{
                "order": {order_json},
                "pageLength": 25,
                "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
                "language": {{
                    "search": "Search all columns:",
                    "lengthMenu": "Show _MENU_ rows",
                    "info": "Showing _START_ to _END_ of _TOTAL_ rows",
                    "infoFiltered": "(filtered from _MAX_ total rows)"
                }}
            }});
        }});
    </script>
</body>
</html>
'''


def get_index_template(reports: dict[str, dict]) -> str:
    """Generate an index page with links to all reports.
    
    Args:
        reports: Dict with report categories as keys, each containing report metadata
                 Example: {'analysis': {'metadata_quality': ('desc', 'file.html', 123)}, ...}
    
    Returns:
        Complete HTML index page as string
    """
    sections_html = []
    
    for category, category_reports in reports.items():
        if not category_reports:
            continue
            
        # Build report cards for this category
        cards_html = []
        for report_name, (description, html_file, count) in category_reports.items():
            # Format the count nicely
            count_str = f"{count:,}" if count is not None else "N/A"
            
            # Choose icon based on report type
            if 'matched' in report_name:
                icon = '✓'
                color = '#34a853'
            elif 'unmatched' in report_name or 'missing' in report_name:
                icon = '✗'
                color = '#ea4335'
            elif 'coverage' in report_name or 'playlist' in report_name:
                icon = '📊'
                color = '#4285f4'
            else:
                icon = '📄'
                color = '#1a73e8'
            
            cards_html.append(f'''
                <a href="{html_file}" class="report-card">
                    <div class="report-icon" style="color: {color}">{icon}</div>
                    <div class="report-info">
                        <h3>{report_name.replace('_', ' ').title()}</h3>
                        <p class="report-desc">{description}</p>
                        <p class="report-count">{count_str} items</p>
                    </div>
                </a>
            ''')
        
        sections_html.append(f'''
            <section class="report-section">
                <h2>{category.replace('_', ' ').title()}</h2>
                <div class="report-grid">
                    {''.join(cards_html)}
                </div>
            </section>
        ''')
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Playlist Sync Matcher - Reports</title>
    
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        html, body {{
            height: 100%;
            min-height: 100%;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }}
        
        header h1 {{
            font-size: 48px;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        header p {{
            font-size: 18px;
            opacity: 0.9;
        }}
        
        .report-section {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        .report-section h2 {{
            color: #1a73e8;
            font-size: 24px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
        }}
        
        .report-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        
        .report-card {{
            display: flex;
            align-items: flex-start;
            padding: 20px;
            background: #f8f9fa;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            text-decoration: none;
            color: inherit;
            transition: all 0.2s ease;
        }}
        
        .report-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-color: #1a73e8;
        }}
        
        .report-icon {{
            font-size: 36px;
            margin-right: 15px;
            flex-shrink: 0;
        }}
        
        .report-info {{
            flex-grow: 1;
        }}
        
        .report-info h3 {{
            font-size: 18px;
            color: #333;
            margin-bottom: 5px;
        }}
        
        .report-desc {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }}
        
        .report-count {{
            font-size: 12px;
            color: #1a73e8;
            font-weight: 600;
        }}
        
        footer {{
            text-align: center;
            color: white;
            margin-top: 40px;
            opacity: 0.8;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Playlist Sync Matcher</h1>
            <p>Comprehensive Reports Dashboard</p>
        </header>
        
        {''.join(sections_html)}
        
        <footer>
            Generated by Playlist Sync Matcher • Click any report to view details
        </footer>
    </div>
</body>
</html>
'''


__all__ = ['get_html_template', 'get_index_template']
