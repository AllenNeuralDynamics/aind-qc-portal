"""Helper functions for converting QCMetric.value fields to Panel components"""
import panel as pn


def value_to_panel(self, name, value):
    """Convert a metric value to a panel object"""

    auto_value = False
    auto_state = False

    if self.type == "checkbox":
        value_widget = pn.widgets.Checkbox(name=name)
    elif self.type == "text":
        value_widget = pn.widgets.TextInput(name=name)
    elif self.type == "float":
        value_widget = pn.widgets.FloatInput(name=name)
    elif self.type == "int":
        value_widget = pn.widgets.IntInput(name=name)
    elif self.type == "list":
        df = pd.DataFrame({"values": value})
        value_widget = pn.pane.DataFrame(df)
        auto_value = True
    elif self.type == "dataframe":
        auto_value = True
        df = pd.DataFrame(df_scalar_to_list(value))
        value_widget = pn.pane.DataFrame(df)
    elif self.type == "custom":
        # Check if this is a custom metric value, and if not give up and just display the JSON
        auto_value = True
        if hasattr(value, "auto_state"):
            auto_state = value.auto_state
        value_widget = value.panel()
    elif self.type == "json":
        value_widget = pn.widgets.JSONEditor(name=name)
    else:
        value_widget = pn.widgets.StaticText(value=f"Can't deal with type {type(value)}")

    return value_widget, auto_value, auto_state
