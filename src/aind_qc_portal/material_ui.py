"""Material UI component wrappers and utilities for QC Portal"""

import os
import panel as pn

# Check if Material UI should be enabled
USE_MATERIAL_UI = os.getenv('USE_MATERIAL_UI', 'true').lower() == 'true'

# AIND brand colors
MATERIAL_THEME = {
    'primary': '#0066CC',      # AIND blue
    'secondary': '#00A896',    # Teal accent
    'error': '#D32F2F',        # Red for failures
    'warning': '#F57C00',      # Orange for pending/warnings
    'success': '#388E3C',      # Green for pass
    'info': '#1976D2',         # Blue for info
}

if USE_MATERIAL_UI:
    try:
        from panel_material_ui import (
            Button,
            TextField, 
            Select,
            Card,
            Chip,
            Alert,
        )
        MATERIAL_AVAILABLE = True
        print("✅ Material UI components loaded successfully")
    except ImportError as e:
        print(f"⚠️ Material UI import failed: {e}")
        MATERIAL_AVAILABLE = False
else:
    MATERIAL_AVAILABLE = False
    print("ℹ️ Material UI disabled via USE_MATERIAL_UI environment variable")


def create_button(name, button_type='primary', **kwargs):
    """Create a button (Material UI or fallback to Panel)"""
    if MATERIAL_AVAILABLE:
        color_map = {
            'primary': 'primary',
            'success': 'success',
            'danger': 'error',
            'warning': 'warning',
            'light': 'default',
        }
        return Button(
            label=name,
            variant='contained',
            color=color_map.get(button_type, 'primary'),
            **kwargs
        )
    else:
        return pn.widgets.Button(
            name=name,
            button_type=button_type,
            **kwargs
        )


def create_text_input(name, placeholder='', multiline=False, **kwargs):
    """Create a text input (Material UI or fallback)"""
    if MATERIAL_AVAILABLE:
        return TextField(
            label=name,
            placeholder=placeholder,
            variant='outlined',
            multiline=multiline,
            fullWidth=True,
            **kwargs
        )
    else:
        if multiline:
            return pn.widgets.TextAreaInput(
                name=name,
                placeholder=placeholder,
                **kwargs
            )
        else:
            return pn.widgets.TextInput(
                name=name,
                placeholder=placeholder,
                **kwargs
            )


def create_select(name, options, **kwargs):
    """Create a select dropdown (Material UI or fallback)"""
    if MATERIAL_AVAILABLE:
        return Select(
            label=name,
            options=options,
            variant='outlined',
            **kwargs
        )
    else:
        return pn.widgets.Select(
            name=name,
            options=options,
            **kwargs
        )


def create_card(title='', children=None, **kwargs):
    """Create a card container (Material UI or fallback)"""
    if MATERIAL_AVAILABLE:
        return Card(
            title=title,
            children=children or [],
            elevation=2,
            **kwargs
        )
    else:
        # Fallback: use Panel Column with custom styling
        content = [pn.pane.Markdown(f"### {title}")] if title else []
        content.extend(children or [])
        return pn.Column(
            *content,
            styles={
                'background': 'white',
                'border-radius': '8px',
                'padding': '16px',
                'box-shadow': '0 2px 4px rgba(0,0,0,0.1)',
            },
            **kwargs
        )


def create_status_chip(status):
    """Create a colored chip for QC status (Material UI or fallback)"""
    color_map = {
        'Pass': 'success',
        'Fail': 'error', 
        'Pending': 'warning',
    }
    
    if MATERIAL_AVAILABLE:
        return Chip(
            label=status,
            color=color_map.get(status, 'default'),
            variant='filled',
            size='small'
        )
    else:
        # Fallback: colored badge using HTML
        bg_color_map = {
            'Pass': MATERIAL_THEME['success'],
            'Fail': MATERIAL_THEME['error'],
            'Pending': MATERIAL_THEME['warning'],
        }
        bg_color = bg_color_map.get(status, '#666')
        
        return pn.pane.HTML(
            f"""
            <span style="
                background-color: {bg_color};
                color: white;
                padding: 4px 12px;
                border-radius: 16px;
                font-size: 12px;
                font-weight: 500;
                display: inline-block;
            ">{status}</span>
            """,
            sizing_mode='fixed',
            width=80,
            height=24
        )


def create_alert(message, severity='info', **kwargs):
    """Create an alert/notification (Material UI or fallback)"""
    if MATERIAL_AVAILABLE:
        return Alert(
            severity=severity,
            children=[pn.pane.Markdown(message)],
            **kwargs
        )
    else:
        # Fallback: use Panel Alert pane
        alert_type_map = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info',
        }
        return pn.pane.Alert(
            message,
            alert_type=alert_type_map.get(severity, 'info'),
            **kwargs
        )