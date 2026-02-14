from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import CurrentUser, DatabaseSession
from src.api.schemas import RefreshTokenRequest, TokenResponse, UserCreate, UserLogin, UserResponse
from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from src.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo usuario",
    description="""
Cria uma nova conta de usuario.

**Requisitos da senha:**
- Minimo 8 caracteres
- Pelo menos 1 letra maiuscula
- Pelo menos 1 numero
- Pelo menos 1 caractere especial (!@#$%^&*...)
    """,
)
async def register(user_data: UserCreate, db: DatabaseSession) -> User:
    """
    Registra um novo usuario no sistema.

    - **email**: Email valido e unico
    - **password**: Senha forte (8+ chars, maiuscula, numero, especial)
    - **name**: Nome do usuario
    """
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        name=user_data.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="""
Autentica o usuario e retorna tokens JWT.

**Uso do token retornado:**
```
Authorization: Bearer {access_token}
```
    """,
)
async def login(credentials: UserLogin, db: DatabaseSession) -> TokenResponse:
    """
    Autentica usuario e retorna access_token + refresh_token.

    - **email**: Email cadastrado
    - **password**: Senha do usuario
    """
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    return TokenResponse(
        access_token=create_access_token(data={"sub": str(user.id), "email": user.email}),
        refresh_token=create_refresh_token(data={"sub": str(user.id)}),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar token",
    description="Usa o refresh_token para obter um novo access_token.",
)
async def refresh_token(request: RefreshTokenRequest, db: DatabaseSession) -> TokenResponse:
    """Renova o access_token usando o refresh_token."""
    payload = verify_token(request.refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(data={"sub": str(user.id), "email": user.email}),
        refresh_token=create_refresh_token(data={"sub": str(user.id)}),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Dados do usuario logado",
    description="Retorna informacoes do usuario autenticado.",
)
async def get_current_user_info(current_user: CurrentUser) -> User:
    """Retorna os dados do usuario autenticado."""
    return current_user
