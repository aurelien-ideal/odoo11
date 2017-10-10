# -*- coding: utf-8 -*-
{
    'name': "Project Forecast",
    'summary': """Resource management for Project""",
    'description': """
    Resource management for Project
    """,
    'category': 'Project',
    'version': '1.0',
    'depends': ['project', 'web_grid', 'hr'],
    'data': [
        'data/project_forecast_data.xml',
        'security/ir.model.access.csv',
        'security/project_forecast_security.xml',
        'views/project_forecast_views.xml',
        'views/project_views.xml',
        'wizard/project_forecast_assignment_views.xml',
    ],
    'demo': [
        'data/project_forecast_demo.xml',
    ],
    'application': True,
    'license': 'OEEL-1',
}
