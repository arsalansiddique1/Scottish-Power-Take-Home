serviceToken = "dev_token_please_rotate"

def auth_header():
    return {"Authorization": f"Bearer {serviceToken}"}
