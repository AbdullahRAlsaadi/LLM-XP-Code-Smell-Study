def __init__(self, conversion, formatting, **kwargs):
    super(PrettyStream, self).__init__(**kwargs)
    self.formatting = formatting
    self.conversion = conversion
    self.mime = self.msg.content_type.split(';')[0]
