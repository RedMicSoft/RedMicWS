from fastapi import APIRouter, Depends, HTTPException, status

from app.users.utils import (
    get_current_user,
    UserModel,
    get_db,
    AsyncSession,
    get_max_lvl,
)
from app.links.models import Link as LinkModel
from app.links.schemas import LinkResponse, LinkCreate
from sqlalchemy import select

router = APIRouter(
    tags=["links"],
    prefix="/links",
)


@router.get("/", response_model=list[LinkResponse])
async def get_links(
    user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    db_links = await db.scalars(select(LinkModel))
    links = db_links.all()

    return links


@router.get("/{link_id}", response_model=LinkResponse)
async def get_link(
    link_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = await db.scalar(select(LinkModel).where(LinkModel.id == link_id))

    return link


@router.post("/", response_model=LinkResponse)
async def create_link(
    link: LinkCreate,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db_link = await db.scalar(
        select(LinkModel).where(LinkModel.link_url == link.link_url)
    )

    if db_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ссылка уже существует."
        )

    new_link = LinkModel(**link.model_dump())

    db.add(new_link)

    await db.commit()
    await db.refresh(new_link)

    return new_link


@router.delete("/{link_id}")
async def delete_link(
    link_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if await get_max_lvl(link_id) < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут удалять ссылки.",
        )

    link = await db.scalar(select(LinkModel).where(LinkModel.id == link_id))
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ссылка не найдена."
        )

    await db.delete(link)
    await db.commit()

    return "Ссылка успешно удалена."
