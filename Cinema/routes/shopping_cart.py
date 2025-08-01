from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from Cinema.models import Cart, CartItem, Movie
from Cinema.config.dependencies import get_db, get_current_user
from Cinema.models import User

router = APIRouter()


@router.post(
    "/{movie_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Add a movie to the current user's cart"
)
async def add_movie_to_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = await db.scalar(select(Cart).where(Cart.user_id == current_user.id))
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        await db.flush()

    # TODO: Simulate purchase check (logic remains the same)
    purchased = False
    if purchased:
        raise HTTPException(
            status_code=400,
            detail="You have already purchased this movie."
        )

    existing = await db.scalar(select(CartItem).where(
        CartItem.cart_id == cart.id,
        CartItem.movie_id == movie_id
    ))
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Movie already in cart."
        )

    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    cart_item = CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item)

    return cart_item




