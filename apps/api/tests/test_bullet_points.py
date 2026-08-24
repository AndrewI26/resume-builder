from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.bullet_points import BulletPoint as BulletPointModel
from schemas.bullet_point import BulletPoint
from services.bullet_points import (
    bullet_points_by_id,
    delete_bullet_points,
    hydrate,
    insert_bullet_points,
)


def bullet(text: str = "First bullet", bolded=()) -> BulletPoint:
    return BulletPoint(text=text, bolded=list(bolded))


def row_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(BulletPointModel)) or 0


def stored(db: Session, bullet_id) -> BulletPointModel:
    db.flush()
    row = db.get(BulletPointModel, bullet_id)
    assert row is not None
    return row


class TestInsertBulletPoints:
    def test_returns_ids_in_payload_order(self, db: Session):
        ids = insert_bullet_points(db, [bullet("First"), bullet("Second")])

        texts = [stored(db, bullet_id).text for bullet_id in ids]
        assert texts == ["First", "Second"]

    def test_inserts_one_row_per_bullet_point(self, db: Session):
        insert_bullet_points(db, [bullet("First"), bullet("Second")])

        assert row_count(db) == 2

    def test_stores_bolded_ranges(self, db: Session):
        ids = insert_bullet_points(db, [bullet("Shipped it", bolded=[(0, 6)])])

        assert stored(db, ids[0]).bolded == [[0, 6]]

    def test_stores_an_empty_bolded_list(self, db: Session):
        ids = insert_bullet_points(db, [bullet("Plain")])

        assert stored(db, ids[0]).bolded == []

    def test_an_empty_payload_inserts_nothing(self, db: Session):
        assert insert_bullet_points(db, []) == []
        assert row_count(db) == 0

    def test_duplicate_text_still_gets_its_own_row(self, db: Session):
        ids = insert_bullet_points(db, [bullet("Same"), bullet("Same")])

        assert len(set(ids)) == 2
        assert row_count(db) == 2


class TestBulletPointsById:
    def test_returns_a_bullet_point_per_id(self, db: Session):
        ids = insert_bullet_points(db, [bullet("First"), bullet("Second")])

        by_id = bullet_points_by_id(db, ids)

        assert {point.text for point in by_id.values()} == {"First", "Second"}

    def test_keys_are_the_stored_ids(self, db: Session):
        ids = insert_bullet_points(db, [bullet("First")])

        assert list(bullet_points_by_id(db, ids)) == ids

    def test_round_trips_bolded_ranges_as_tuples(self, db: Session):
        ids = insert_bullet_points(db, [bullet("Shipped it", bolded=[(0, 6)])])

        assert bullet_points_by_id(db, ids)[ids[0]].bolded == [(0, 6)]

    def test_no_ids_means_no_query(self, db: Session):
        assert bullet_points_by_id(db, []) == {}

    def test_unknown_ids_are_simply_absent(self, db: Session):
        ids = insert_bullet_points(db, [bullet("First")])

        by_id = bullet_points_by_id(db, [*ids, uuid4()])

        assert list(by_id) == ids

    def test_a_repeated_id_is_looked_up_once(self, db: Session):
        ids = insert_bullet_points(db, [bullet("First")])

        assert list(bullet_points_by_id(db, [ids[0], ids[0]])) == ids


class TestDeleteBulletPoints:
    def test_deletes_the_addressed_rows(self, db: Session):
        ids = insert_bullet_points(db, [bullet("First"), bullet("Second")])

        delete_bullet_points(db, ids)

        assert row_count(db) == 0

    def test_leaves_other_rows_alone(self, db: Session):
        doomed = insert_bullet_points(db, [bullet("First")])
        kept = insert_bullet_points(db, [bullet("Second")])

        delete_bullet_points(db, doomed)

        assert list(bullet_points_by_id(db, kept)) == kept

    def test_no_ids_is_a_no_op(self, db: Session):
        insert_bullet_points(db, [bullet("First")])

        delete_bullet_points(db, [])

        assert row_count(db) == 1

    def test_unknown_ids_are_ignored(self, db: Session):
        kept = insert_bullet_points(db, [bullet("First")])

        delete_bullet_points(db, [uuid4()])

        assert list(bullet_points_by_id(db, kept)) == kept

    def test_a_repeated_id_deletes_once_without_error(self, db: Session):
        ids = insert_bullet_points(db, [bullet("First")])

        delete_bullet_points(db, [ids[0], ids[0]])

        assert row_count(db) == 0


class TestHydrate:
    def test_resolves_ids_in_stored_order(self):
        first, second = uuid4(), uuid4()
        by_id = {first: bullet("First"), second: bullet("Second")}

        assert [point.text for point in hydrate([second, first], by_id)] == [
            "Second",
            "First",
        ]

    def test_drops_ids_that_are_missing(self):
        known = uuid4()
        by_id = {known: bullet("First")}

        assert hydrate([uuid4(), known], by_id) == [by_id[known]]

    def test_repeats_an_id_that_appears_twice(self):
        known = uuid4()
        by_id = {known: bullet("First")}

        assert hydrate([known, known], by_id) == [by_id[known], by_id[known]]

    def test_no_ids_gives_no_bullet_points(self):
        assert hydrate([], {uuid4(): bullet()}) == []

    def test_an_empty_map_drops_everything(self):
        assert hydrate([uuid4()], {}) == []


class TestBoldedRanges:
    """Offsets are inclusive on both ends, and must be sorted and disjoint."""

    def test_an_inclusive_range_covers_its_end_character(self):
        # (0, 6) over a 10 character string bolds "Shipped", not "Shippe"
        text = "Shipped it"
        start, end = bullet(text, bolded=[(0, 6)]).bolded[0]

        assert text[start : end + 1] == "Shipped"

    def test_accepts_adjacent_ranges(self):
        assert bullet("abcdef", bolded=[(0, 1), (2, 3)]).bolded == [(0, 1), (2, 3)]

    def test_accepts_a_single_character_range(self):
        assert bullet("abc", bolded=[(1, 1)]).bolded == [(1, 1)]

    def test_accepts_a_range_ending_at_the_last_character(self):
        assert bullet("abc", bolded=[(0, 2)]).bolded == [(0, 2)]

    @pytest.mark.parametrize(
        ("bolded", "reason"),
        [
            ([(3, 1)], "inverted"),
            ([(-1, 2)], "negative start"),
            ([(0, -1)], "negative end"),
            ([(0, 3)], "end past the last index"),
            ([(3, 3)], "start past the last index"),
            ([(2, 3), (0, 1)], "out of order"),
            ([(0, 2), (1, 2)], "overlapping"),
            ([(0, 2), (2, 2)], "touching at a shared index"),
        ],
    )
    def test_rejects_invalid_ranges(self, bolded, reason):
        with pytest.raises(ValidationError):
            bullet("abc", bolded=bolded)
