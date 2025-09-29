from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.models import get_session, User, RSSConfig
from models.db_operations import DBOperations
import jwt
from datetime import datetime, timedelta
import pytz
from utils.constants import DEFAULT_TIMEZONE
from typing import Optional
from sqlalchemy.orm import joinedload
import models.models as models
import os
import secrets

router = APIRouter()
templates = Jinja2Templates(directory="rss/app/templates")
db_ops = None

# JWT 配置
SECRET_KEY = secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24小时

def init_db_ops():
    global db_ops
    if db_ops is None:
        db_ops = DBOperations()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    tz = pytz.timezone(DEFAULT_TIMEZONE)
    if expires_delta:
        expire = datetime.now(tz) + expires_delta
    else:
        expire = datetime.now(tz) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except jwt.PyJWTError:
        return None
    
    db_session = get_session()
    try:
        init_db_ops()
        user = await db_ops.get_user(db_session, username)
        return user
    finally:
        db_session.close()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    db_session = get_session()
    try:
        # 检查是否有任何用户存在
        users = db_session.query(User).all()
        if not users:
            return RedirectResponse(url="/register", status_code=status.HTTP_302_FOUND)
        return templates.TemplateResponse("login.html", {"request": request})
    finally:
        db_session.close()

@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    response: Response = None
):
    db_session = get_session()
    try:
        init_db_ops()
        user = await db_ops.verify_user(db_session, form_data.username, form_data.password)
        if not user:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "用户名或密码错误"},
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return response
    finally:
        db_session.close()

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    db_session = get_session()
    try:
        # 检查是否已有用户
        users = db_session.query(User).all()
        if users:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        return templates.TemplateResponse("register.html", {"request": request})
    finally:
        db_session.close()

@router.post("/register")
async def register(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    confirm_password = form_data.get("confirm_password")
    
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "两次输入的密码不一致"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    db_session = get_session()
    try:
        init_db_ops()
        user = await db_ops.create_user(db_session, username, password)
        if not user:
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "创建用户失败"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return response
    finally:
        db_session.close()

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # 直接重定向到 RSS 仪表盘
    return RedirectResponse(url="/rss/dashboard", status_code=status.HTTP_302_FOUND)

@router.post("/rss/change_password")
async def change_password(
    request: Request,
    user = Depends(get_current_user),
):
    """修改用户密码"""
    if not user:
        return JSONResponse(
            {"success": False, "message": "未登录或会话已过期"}, 
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        form_data = await request.form()
        current_password = form_data.get("current_password")
        new_password = form_data.get("new_password")
        confirm_password = form_data.get("confirm_password")
        
        # 验证表单数据
        if not current_password:
            return JSONResponse({"success": False, "message": "请输入当前密码"})
        
        if not new_password:
            return JSONResponse({"success": False, "message": "请输入新密码"})
        
        if len(new_password) < 8:
            return JSONResponse({"success": False, "message": "新密码长度必须至少为8个字符"})
        
        if new_password != confirm_password:
            return JSONResponse({"success": False, "message": "新密码和确认密码不一致"})
        
        # 验证当前密码
        db_session = get_session()
        try:
            init_db_ops()
            is_valid = await db_ops.verify_user(db_session, user.username, current_password)
            if not is_valid:
                return JSONResponse({"success": False, "message": "当前密码不正确"})
            
            # 更新密码
            success = await db_ops.update_user_password(db_session, user.username, new_password)
            if not success:
                return JSONResponse({"success": False, "message": "修改密码失败，请重试"})
            
            return JSONResponse({"success": True, "message": "密码修改成功"})
        finally:
            db_session.close()
    except Exception as e:
        return JSONResponse({"success": False, "message": f"修改密码出错: {str(e)}"}) 