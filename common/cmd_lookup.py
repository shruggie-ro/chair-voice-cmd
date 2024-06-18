
# ===================================== English(en-us) ====================================
cmd_table_en = {
    'hey chair': 'hey_chair',
    'hey chair recliner down': 'hey_chair_recliner_down',
    'hey chair recliner lower': 'hey_chair_recliner_down',
    'hey chair recliner up': 'hey_chair_recliner_up',
    'hey chair recliner raise': 'hey_chair_recliner_up',
    'hey chair stop': 'stop',
    'recliner raise': 'recliner_up',
    'recliner lower': 'recliner_down',
    'recliner up': 'recliner_up',
    'recliner down': 'recliner_down',
    'stop': 'stop',
}


def build_dict_en(cmd_table):
    """This is for English.

    Build a custom list of words from cmd_table for vosk model to choose from when recognizing.

    Parameters
    ----------
    cmd_table : dict{ str:str }
        Description as above.

    Returns
    -------
    d : str
        The str form of a custom list of words.
    """

    # return '["get status down please walk sit forward check rest stand up run stop", "[unk]"]'
    # print("[\"get status down please walk sit forward check rest stand up run stop\", \"[unk]\"]")
    d = []
    keys = cmd_table.keys()
    for k in keys:
        d += k.split(' ')
    d = list(set(d))
    d = [" ".join(d), "[unk]"]
    d = str(d).replace("'", "\"")
    print(d)
    return d
# ===================================== English(en-us) ====================================


def text2cmd(text, cmd_table):
    """Convert the result of speech recognition into Petoi command.

    Parameters
    ----------
    text : str
        The result from vosk model after speech recognition.

    cmd_table : dict{ str:str }
        Description as above.

    Returns
    -------
    An str. The corresponding Petoi command.
    """

    for k in cmd_table.keys():
        if (text.find(k) > -1):
            return cmd_table.get(k, '')

    return ''
