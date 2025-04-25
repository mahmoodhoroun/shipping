{
    'name': 'Shipping Integration',
    'version': '1.0',
    'depends': ['base', 'stock'],
    'data': [
        'data/ir_cron_data.xml',
        # 'reports/delivery_report.xml',
        'views/stock_picking_views.xml',
             ],
    'assets': {
        'web.assets_backend': [
            'shipping_integration/static/**/*',  # Make static resources accessible
        ],
    },
    'installable': True,
}