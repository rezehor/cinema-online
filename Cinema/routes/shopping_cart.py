from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload, joinedload
from Cinema.models import Cart, CartItem, Movie, OrderItem, Order, OrderStatusEnum
from Cinema.config.dependencies import get_db, get_current_user
from Cinema.models import User
from Cinema.schemas.shopping_cart import CartMoviesResponseSchema, AdminAllCartsResponseSchema, AdminUserCartSchema

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

    purchased_stmt = (
        select(OrderItem)
        .join(Order)
        .where(
            OrderItem.movie_id == movie_id,
            Order.user_id == current_user.id,
            Order.status == OrderStatusEnum.PAID
        )
    )
    already_purchased = (await db.execute(purchased_stmt)).first()
    if already_purchased:
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
    if not movie or not movie.is_available:
        raise HTTPException(
            status_code=404,
            detail="Movie not found or not available for purchase."
        )

    cart_item = CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item)

    return {"message": "Movie added to cart successfully."}


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = await db.scalar(select(Cart).where(Cart.user_id == current_user.id))
    if cart:
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.commit()


@router.delete("/remove/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_movie_from_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = await db.scalar(select(Cart).where(Cart.user_id == current_user.id))
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    await db.execute(
        delete(CartItem)
        .where(CartItem.cart_id == cart.id, CartItem.movie_id == movie_id)
    )
    await db.commit()


@router.get(
    "/",
    response_model=CartMoviesResponseSchema,
    summary="Get list of movies in the user's cart"
)
async def get_movies_in_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = await db.scalar(
        select(Cart)
        .options(
            selectinload(Cart.cart_items)
            .joinedload(CartItem.movie)
            .joinedload(Movie.genres)
        )
        .where(Cart.user_id == current_user.id)
    )

    if not cart or not cart.cart_items:
        return {"movies": []}

    movies = [item.movie for item in cart.cart_items]
    return CartMoviesResponseSchema(movies=movies)
    available_movies = [
        item.movie for item in cart.cart_items
        if item.movie and item.movie.is_available
    ]

    return CartMoviesResponseSchema(movies=available_movies)

