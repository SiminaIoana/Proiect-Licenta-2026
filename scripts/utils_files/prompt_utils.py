

def safe_format(template: str, **kwargs):
    # escape toate {} din template
    template = template.replace("{", "{{").replace("}", "}}")

    # reintrodu doar variabilele corecte
    for key in kwargs:
        template = template.replace("{{" + key + "}}", "{" + key + "}")

    return template.format(**kwargs)
