from xml.etree.ElementTree import Element, tostring, indent
from collections import UserDict, UserList


def to_xml(sxpb_data: UserDict) -> str:
    """Converts an SxpbDict object to an XML string."""

    def build_element(tag, data):
        attributes = {}
        children_data = []
        text_content = None

        if isinstance(data, (dict, UserDict)):
            for key, value in data.items():
                if key.startswith("@"):
                    attributes[key[1:]] = str(value)
                elif key == "$":
                    children_data = value
                elif key == "$t":  # For text content
                    text_content = str(value)
                else:
                    # Treat as a child element (for non-badgerfish compatibility)
                    if isinstance(value, (list, UserList)):
                        for item in value:
                            children_data.append({key: item})
                    else:
                        children_data.append({key: value})
        else:
            # Data is a scalar, treat as text content
            text_content = str(data)

        element = Element(tag, attributes)
        if text_content:
            element.text = text_content

        if isinstance(children_data, (list, UserList)):
            for child_lone in children_data:
                if isinstance(child_lone, (dict, UserDict)):
                    for child_tag, child_value in child_lone.items():
                        child_element = build_element(child_tag, child_value)
                        element.append(child_element)

        return element

    root_tag, root_data = next(iter(sxpb_data.items()))
    root_element = build_element(root_tag, root_data)
    indent(root_element, space="  ")

    return tostring(root_element, encoding="unicode", xml_declaration=True)
