# -*- coding: utf-8 -*-
{
    'name': 'Jira Project Management',
    'version': '18.0.1.0.0',
    'category': 'Project',

    'summary': 'Jira-style Project Management with Scrum',
    'description': """
        Jira-Style Project Management System
        =====================================

        Features:
        ---------
        * Projects with team management
        * Sprint Planning & Management
        * Tickets (Story, Task, Bug, Epic, Subtask)
        * Customizable Workflow States
        * Kanban Boards with drag & drop
        * Burndown Charts
        * Time Tracking
        * Sub-tasks and Linked Issues

        Perfect for Agile/Scrum teams!
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',

    # Dependencies
    'depends': [
        'base',
        'mail',
        'web',
    ],

    # Data files - loaded in order
    'data': [
        # Security (ALWAYS FIRST!)
        'security/jira_groups.xml',
        'security/jira_security.xml',

        'security/ir.model.access.csv',
     'data/jira_cron.xml',
    'views/jira_report_views.xml',
    'report/jira_sprint_report.xml',



        # Data
        'data/sequence.xml',
        'data/ir_rule.xml',


        # Views (order matters for dependencies)
        'views/jira_workflow_views.xml',
        'views/jira_project_views.xml',
        'views/jira_ticket_views.xml',
        'views/view_jira_ticket_kanban.xml',
        'views/jira_sprint_views.xml',
        'views/jira_dashboard_views.xml',

        # Menus
        'views/jira_menus.xml',
    ],

    # Assets - CSS & JavaScript
    'assets': {
        'web.assets_backend': [
            'jira_project/static/src/js/chart.umd.min.js',
            # JavaScript
            'jira_project/static/src/js/dashboard_chart.js',
             'jira_project/static/src/js/ticket_status_donut.js',
              'jira_project/static/src/js/sprint_burndown_v2.js',

            # CSS
            'jira_project/static/src/css/sprint_kanban.css',
             'jira_project/static/src/css/Tickets_kanban.css',
              'jira_project/static/src/css/navbar.css',
            'jira_project/static/src/css/dashboard.css',
        ],
    },

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}