from datetime import date

from fastapi import APIRouter, status, HTTPException, Depends, Query, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from .schemas import (
    UserResponse,
    UserCreate,
    UsersResponse,
    ContactResponse,
    UserUpdate,
    RestCreate,
    RestResponse,
    UpdateUserPassword,
)
from .models import User as UserModel, Contacts as ContactModel
from .utils import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_max_lvl,
    update_avatar,
    update_demo,
    get_id_deleted_user,
    save_role_image,
)
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload, with_loader_criteria
from app.levels.models import Level, UserLevel
from app.levels.schemas import LevelResponse
from app.roles.schemas import RoleHistoryResponse, RoleHistoryCreate
from app.roles.models import RoleHistory, Role

router = APIRouter(prefix="/users", tags=["users"])

DELETED_USER_ID = -1


@router.get("/", response_model=list[UsersResponse])
async def get_users(
    role_filter: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Выводит информацию о всех пользователях.\n
    По умолчанию level_filter = None(null).\n
    Если указано значение(наименование роли), то будут выведены пользователи только с указанной ролью.\n
    """
    if role_filter is not None:
        db_users = (
            select(UserModel)
            .join(UserLevel, UserLevel.user_id == UserModel.user_id)
            .join(Level, Level.level_id == UserLevel.level_id)
            .where(Level.role_name == role_filter)
        )

    else:
        db_users = select(UserModel).where(UserModel.user_id != DELETED_USER_ID)

    db_users = db_users.options(
        selectinload(UserModel.contacts),
        selectinload(UserModel.team_roles),
        with_loader_criteria(Level, Level.access_level != 0),
    )
    users = await db.scalars(db_users)

    return [UsersResponse.model_validate(user) for user in users.all()]


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Выводит подробную информацию о пользователе, включая список его ролей и макс левел.
    """
    db_user = await db.scalar(
        select(UserModel)
        .where(UserModel.user_id == user_id)
        .options(
            selectinload(UserModel.contacts),
            selectinload(UserModel.team_roles),
            selectinload(UserModel.history),
            with_loader_criteria(Level, Level.access_level != 0),
        )
    )
    if not db_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    user_data = {
        k: v
        for k, v in db_user.__dict__.items()
        if not k.startswith("_") and not k.startswith("rest")
    }
    del user_data["hashed_password"]
    if db_user.rest_start:
        user_data["rest"] = {
            "rest_start": db_user.rest_start,
            "rest_end": db_user.rest_end,
            "rest_reason": db_user.rest_reason,
        }
    else:
        user_data["rest"] = None
    if db_user.history:
        user_data["roles"] = db_user.history
    else:
        user_data["roles"] = None
    response = UserResponse(**user_data)
    return {"User": response, "accessLevel": await get_max_lvl(db, db_user)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: UserModel = Depends(get_current_user),
):
    """
    Эндпоинт для прода. Предполагает уже созданного админа в БД. В разработке использовать POST users/create. \n
    В users/create не нужно использовать авторизацию для создания пользователей. В проде уберем. \n
    Регистрация нового пользователя с уровнем доступа от 1 до 3 и хэш. пароля. \n
    Ошибка 400 если email уже есть в БД. \n
    Ошибка 400 если юзер не админ. \n
    Только пользователь с access_level 3 может получить доступ.
    """
    if await get_max_lvl(db, admin) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Только админы могут создавать пользователей",
        )
    role = await db.scalar(
        select(Level).where(Level.access_level == 0, Level.is_active == True)
    )

    db_user = await db.scalar(
        select(UserModel).where(UserModel.nickname == user.nickname)
    )

    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Никнейм уже зарегистрирован",
        )

    db_user = UserModel(
        **user.model_dump(exclude={"password", "contacts"}),
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    await db.flush()

    for contact in user.contacts:
        db.add(
            ContactModel(
                user_id=db_user.user_id, title=contact.title, link=contact.link
            )
        )

    user_role = UserLevel(level_id=role.level_id, user_id=db_user.user_id)
    db.add(user_role)
    await db.commit()

    return {"User": db_user, "role": role}


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """
    Аутентифицирует пользователя и возвращает access_token.
    Токен длится 30 дней.
    """
    db_user = await db.scalars(
        select(UserModel)
        .where(UserModel.nickname == form_data.username)
        .options(
            selectinload(UserModel.team_roles),
            selectinload(UserModel.contacts),
        )
    )
    user = db_user.first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный никнейм или пароль.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"id": user.user_id})

    return {
        "User": UsersResponse.model_validate(user),
        "access_token": access_token,
        "accessLevel": await get_max_lvl(db, user),
    }


#
@router.post(
    "/{user_id}/level",
    status_code=status.HTTP_200_OK,
    response_model=list[LevelResponse],
)
async def add_user_level(
    user_id: int,
    levels: list[int],
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Добавляет роль пользователю.\n
    Возвращает список ролей.\n
    Только для 3 лвл+.\n
    """
    if await get_max_lvl(db, user) < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав.",
        )

    db_user = await db.scalar(
        select(UserModel).where(
            UserModel.user_id == user_id,
        )
    )
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден."
        )

    db_roles = await db.scalars(
        select(Level).where(
            Level.level_id.in_(levels),
            Level.is_active == True,
            Level.access_level != 4,
            Level.access_level != 0,
        )
    )
    roles = db_roles.all()
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Роли не найдены"
        )

    for role in roles:
        if role.access_level >= await get_max_lvl(db, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно выдавать роли только ниже своей роли.",
            )
        new_role = UserLevel(level_id=role.level_id, user_id=user_id)
        db.add(new_role)

    await db.commit()
    roles_list = await db.scalars(
        select(Level)
        .join(UserLevel)
        .where(UserLevel.user_id == user_id, UserLevel.level_id != 6)
    )

    return roles_list.all()


@router.patch("/{user_id}", status_code=status.HTTP_200_OK)
async def update_user(
    user_id: int,
    upd_user: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 3 and user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец страницы и администраторы могут редактировать эту страницу.",
        )

    nickname_exist = await db.scalar(
        select(UserModel.nickname).where(UserModel.nickname == upd_user.nickname)
    )
    if nickname_exist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Данный никнейм уже занят."
        )

    db_user = await db.scalar(
        select(UserModel)
        .where(UserModel.user_id == user_id)
        .options(selectinload(UserModel.contacts))
    )
    new_contacts = upd_user.__dict__.pop("contacts")
    if new_contacts:
        exist_contacts = {c.title: c for c in db_user.contacts}

        for new_contact in new_contacts:
            if new_contact.title in exist_contacts:
                exist_contacts[new_contact.title].link = new_contact.link
                del exist_contacts[new_contact.title]
            else:
                db.add(ContactModel(**new_contact.model_dump(), user_id=user_id))

        for contact in exist_contacts.values():
            await db.delete(contact)

    if any([change for change in upd_user.__dict__.values()]):
        await db.execute(
            update(UserModel)
            .where(UserModel.user_id == user_id)
            .values(**upd_user.model_dump(exclude={"contacts"}, exclude_unset=True))
        )

    await db.refresh(db_user, ["contacts"])
    await db.commit()

    db_user.__dict__.pop("hashed_password")
    return db_user


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только гл. администраторы могут удалять пользователей.",
        )

    user_for_delete = await db.get(UserModel, user_id)
    if not user_for_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не существует"
        )

    if user_for_delete.user_id == get_id_deleted_user():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя удалить удалённого пользователя.",
        )

    if await get_max_lvl(db, user_for_delete) >= await get_max_lvl(db, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Запрещено.")

    await db.delete(user_for_delete)
    await db.commit()

    return f"Пользователь был удалён."


@router.put("/{user_id}/avatar", status_code=status.HTTP_200_OK)
async def update_user_avatar(
    user_id: int,
    avatar: UploadFile,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 3 and user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец страницы и администраторы могут сменить эту аватарку.",
        )

    user = await db.get(UserModel, user_id)
    user.avatar_url = await update_avatar(avatar, user.avatar_url)

    await db.commit()
    await db.refresh(user)

    return user.avatar_url


@router.put("/{user_id}/demo", status_code=status.HTTP_200_OK)
async def update_user_demo(
    user_id: int,
    demo: UploadFile,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 3 and user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец страницы и администраторы могут сменить эту аватарку.",
        )

    user = await db.get(UserModel, user_id)
    user.demo_url = await update_demo(demo, user.demo_url)

    await db.commit()
    await db.refresh(user)

    return user.demo_url


@router.post(
    "/{user_id}/rest", status_code=status.HTTP_201_CREATED, response_model=RestResponse
)
async def create_rest(
    rest: RestCreate,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 2 and user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец страницы или куратор и выше могут создать этот рест.",
        )

    db_user = await db.scalar(select(UserModel).where(UserModel.user_id == user_id))

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Такого пользователя не существует.",
        )

    if rest.rest_start < date.today() and rest.rest_end < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя установить рест в прошлое)",
        )

    if rest.rest_start > rest.rest_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата начала реста должна быть не больше даты конца реста.",
        )

    await db.execute(
        update(UserModel)
        .where(UserModel.user_id == user_id)
        .values(**rest.model_dump())
    )
    if rest.rest_start <= date.today():
        db_user.is_active = False

    await db.commit()
    await db.refresh(db_user)

    db_user.__dict__.pop("hashed_password")
    return db_user


@router.delete("/{user_id}/rest", status_code=status.HTTP_200_OK)
async def delete_rest(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 2 and user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец страницы или куратор и выше могут удалить этот рест.",
        )

    db_user = await db.scalar(select(UserModel).where(UserModel.user_id == user_id))

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Такого пользователя не существует.",
        )

    db_user.rest_start = None
    db_user.rest_end = None
    db_user.rest_reason = None
    db_user.is_active = True

    await db.commit()
    await db.refresh(db_user)

    db_user.__dict__.pop("hashed_password")
    return db_user


@router.delete("/{user_id}/levels/{level_id}", status_code=status.HTTP_200_OK)
async def delete_level(
    user_id: int,
    level_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут менять пользователям роли.",
        )

    db_user = await db.scalar(select(UserModel).where(UserModel.user_id == user_id))
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден."
        )

    db_level = await db.get(Level, level_id)
    if not db_level:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    if db_level.access_level == 4 or db_level.access_level == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Данную роль удалить нельзя."
        )

    user_level = await db.get(UserLevel, (db_level.level_id, db_user.user_id))
    if not user_level:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="У пользователя нет данной роли.",
        )

    await db.delete(user_level)
    await db.commit()
    await db.refresh(db_user)

    db_user = await db.scalar(
        select(UserModel)
        .where(UserModel.user_id == user_id)
        .options(
            selectinload(UserModel.team_roles),
            with_loader_criteria(Level, Level.level_id != 6),
        )
    )

    return db_user.team_roles


@router.post("/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def add_role(
    user_id: int,
    image: UploadFile | None = None,
    role: RoleHistoryCreate = Depends(RoleHistoryCreate.as_form),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Роль в историю может добавить только куратор и выше.",
        )

    db_user = await db.scalar(select(UserModel).where(UserModel.user_id == user_id))

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден."
        )

    role_exist_in_history = await db.scalar(
        select(RoleHistory).where(
            RoleHistory.user_id == user_id,
            RoleHistory.role_name == role.role_name,
            RoleHistory.project_name == role.project_name,
        )
    )
    if role_exist_in_history:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Роль уже есть у пользователя.",
        )

    new_role = RoleHistory(**role.model_dump(), user_id=user_id)
    if image:
        image_url = await save_role_image(image)
        new_role.image_url = image_url

    db.add(new_role)

    await db.commit()

    return new_role


@router.delete("/roles/{role_id}", status_code=status.HTTP_200_OK)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только куратор и выше могут удалить роль.",
        )

    db_role = await db.get(RoleHistory, role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    await db.delete(db_role)
    await db.commit()

    return "Роль была удалена."


@router.patch("/{user_id}/password")
async def change_user_password(
    user_id: int,
    new_password: UpdateUserPassword,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 4:
        raise HTTPException(status_code=403)

    db_user = await db.scalar(select(UserModel).where(UserModel.user_id == user_id))
    if not db_user:
        raise HTTPException(status_code=404)
    if await get_max_lvl(db, db_user) >= 4:
        raise HTTPException(status_code=403)

    db_user.hashed_password = hash_password(new_password.new_password)
    await db.commit()

    await db.refresh(db_user)

    return "Пароль успешно изменен."
