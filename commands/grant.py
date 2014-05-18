config = {
    "access": "public",
    "help": ".grant [name] [permission, ...] || .grant buttface admin staff || Grants a user permissions",
    "reverse_help": ".ungrant [name] [permission, ...] || .ungrant buttface admin staff || Remove a user's permissions"
}

def command(guid, manager, irc, channel, user, name, permissions, reverse = False, admin_mode = False):
    owned = yield manager.getPermissions(user)
    permissions = permissions.split(" ")
    method = "ungrantPermission" if reverse else "grantPermission"

    if reverse and not admin_mode:
        irc.msg(channel, u"You must be an admin to remove permissions")
        return

    results = [[],[]]
    for permission in permissions:
        if not reverse and permission not in owned:
            irc.msg(channel, u"You must have a permission, specifically \"{}\", to grant it to another.".format(permission))
            continue

        result = yield getattr(manager.master.modules["db"], method)(name, permission)
        results[int(result)].append(permission)

    message = []
    if results[1]:
        message.append(u"{} {} to {}.".format(u"Ungranted" if reverse else u"Granted", u", ".join(results[1]), name))
    if results[0]:
        message.append(u"Failed to {} {} to {}. User or Permission is invalid.".format(u"ungrant" if reverse else u"grant", u", ".join(results[0]), name))
    irc.msg(channel, u" ".join(message))
