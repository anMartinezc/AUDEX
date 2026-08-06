def es_administrador_productos(usuario):
    if not usuario.is_authenticated:
        return False

    return (
        usuario.is_superuser
        or usuario.is_staff
        or usuario.groups.filter(
            name="Administradores"
        ).exists()
    )