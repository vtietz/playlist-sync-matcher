"""HTML report template generation with jQuery DataTables."""
from typing import Optional


def get_html_template(
    title: str, 
    columns: list[str], 
    rows: list[list], 
    description: str = "",
    default_order: Optional[list[list[int | str]]] = None,
    csv_filename: Optional[str] = None,
    show_navigation: bool = True,
    active_page: Optional[str] = None
) -> str:
    """Generate a DataTables-powered HTML report with pagination and search.
    
    Args:
        title: Report title
        columns: List of column headers
        rows: List of row data (each row is a list of cell values)
        description: Optional description text shown above the table
        default_order: Default sort order as [[col_idx, 'asc'/'desc'], ...]. 
                      Example: [[0, 'desc'], [1, 'asc']] sorts by col 0 DESC, then col 1 ASC
        csv_filename: Optional CSV filename for download button (e.g., "report.csv")
        show_navigation: Whether to show the top navigation bar (default: True)
        active_page: Which page is currently active for navigation highlighting 
                    (e.g., "matched_tracks", "unmatched_albums", etc.)
    
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
    
    # CSV download button HTML
    download_btn_html = ""
    if csv_filename:
        download_btn_html = f'<a href="{csv_filename}" class="download-btn" download>📥 Download CSV</a>'
    
    # Navigation HTML - determine path prefix based on directory depth
    # For playlist detail pages (in playlists/ subdirectory), we need to go up one level (../)
    # We detect this by checking if csv_filename doesn't contain a slash
    # (because main reports have simple filenames like "matched_tracks.csv",
    #  while playlist details just have "{id}.csv" when in the playlists/ dir)
    nav_prefix = ""
    if show_navigation and csv_filename:
        # If we're rendering from within a subdirectory, we need to go up
        # Main reports have full paths like "matched_tracks.csv" (no slash)
        # Playlist details are rendered with just "playlist_id.csv" after being placed in playlists/
        # So if the filename looks like a UUID/ID (contains no underscore), it's in a subdir
        if "_" not in csv_filename and "/" not in csv_filename and "\\" not in csv_filename:
            nav_prefix = "../"
    
    # Helper to add 'active' class to current page
    def nav_class(page_name: str) -> str:
        return ' class="active"' if active_page == page_name else ''
    
    nav_html = ""
    if show_navigation:
        nav_html = f'''
    <nav class="nav-bar">
        <div class="nav-container">
            <a href="{nav_prefix}index.html" class="nav-home">🏠 Home</a>
            <div class="nav-links">
                <a href="{nav_prefix}matched_tracks.html"{nav_class("matched_tracks")}>✓ Matched Tracks</a>
                <a href="{nav_prefix}unmatched_tracks.html"{nav_class("unmatched_tracks")}>✗ Unmatched Tracks</a>
                <a href="{nav_prefix}unmatched_albums.html"{nav_class("unmatched_albums")}>💿 Unmatched Albums</a>
                <a href="{nav_prefix}playlist_coverage.html"{nav_class("playlist_coverage")}>📊 Playlist Coverage</a>
                <a href="{nav_prefix}metadata_quality.html"{nav_class("metadata_quality")}>🔍 Metadata Quality</a>
            </div>
        </div>
    </nav>
    '''
    
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
        
        /* Navigation Bar */
        .nav-bar {{
            background: #1a73e8;
            padding: 0;
            margin: 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .nav-container {{
            max-width: 1600px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            padding: 0;
        }}
        
        .nav-home {{
            padding: 15px 20px;
            background: #1557b0;
            color: white;
            text-decoration: none;
            font-weight: 600;
            transition: background 0.2s ease;
            border-right: 1px solid rgba(255,255,255,0.2);
        }}
        
        .nav-home:hover {{
            background: #0d3c7a;
            color: white;
            text-decoration: none;
        }}
        
        .nav-links {{
            display: flex;
            flex-wrap: wrap;
            flex: 1;
        }}
        
        .nav-links a {{
            padding: 15px 20px;
            color: white;
            text-decoration: none;
            transition: background 0.2s ease;
            border-right: 1px solid rgba(255,255,255,0.1);
        }}
        
        .nav-links a:hover {{
            background: #1557b0;
            color: white;
            text-decoration: none;
        }}
        
        .nav-links a.active {{
            background: #0d3c7a;
            font-weight: 600;
            border-bottom: 3px solid #fff;
        }}
        
        .nav-links a:last-child {{
            border-right: none;
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
        
        .header-section {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        
        .download-btn {{
            background: #1a73e8;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            transition: background 0.2s ease;
        }}
        
        .download-btn:hover {{
            background: #1557b0;
            color: white;
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
        
        /* Standardized Badge System */
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            text-align: center;
            white-space: nowrap;
        }}
        
        /* Status Priority (Green = Best, Red = Worst) */
        .badge-success {{
            background: #28a745;
            color: white;
        }}
        
        .badge-primary {{
            background: #007bff;
            color: white;
        }}
        
        .badge-warning {{
            background: #ffc107;
            color: #212529;
        }}
        
        .badge-danger {{
            background: #dc3545;
            color: white;
        }}
        
        .badge-secondary {{
            background: #6c757d;
            color: white;
        }}
        
        /* Path display with tooltips */
        .path-short {{
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            cursor: help;
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
        
        /* Loading indicator */
        #loading-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            flex-direction: column;
        }}
        
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1a73e8;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        .loading-text {{
            margin-top: 20px;
            color: #1a73e8;
            font-size: 16px;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <!-- Loading overlay -->
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="loading-text">Loading table data...</div>
    </div>
    
    {nav_html}
    <div class="container">
        <div class="header-section">
            <h1>{title}</h1>
            {download_btn_html}
        </div>
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
            // Initialize DataTable
            var table = $('#dataTable').DataTable({{
                "order": {order_json},
                "pageLength": 25,
                "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
                "language": {{
                    "search": "Search all columns:",
                    "lengthMenu": "Show _MENU_ rows",
                    "info": "Showing _START_ to _END_ of _TOTAL_ rows",
                    "infoFiltered": "(filtered from _MAX_ total rows)"
                }},
                "initComplete": function(settings, json) {{
                    // Hide loading overlay when DataTable is fully initialized
                    $('#loading-overlay').fadeOut(300);
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
