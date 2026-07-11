def str_to_type(value):
    return 2 if value == '目标检测' else None


def type_to_str(value):
    return '目标检测' if value == 2 else ''


def items_handle(items):
    for item in items:
        if 'type' in item:
            item['type'] = type_to_str(item['type'])
