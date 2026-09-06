"""Cross-tenant isolation.

These tests exist because the pre-rewrite code enforced isolation by
convention — application code remembered to add ``user_id=eq.X``. The two
failure modes that produces are exactly what is pinned here:

* forgetting the filter (leak), and
* trusting an id supplied by the client (takeover).

Isolation now happens in the database via RLS; the fake engine enforces the
same contract, so a regression fails here just as it would against Postgres.
"""

from __future__ import annotations

import pytest

from cn_social_agent.core import AdminError, clear
from cn_social_agent.core.admin import AdminGateway
from cn_social_agent.core.db import RlsViolation, TenantDB
from cn_social_agent.core.tenant import TenantContext, TenantError, bind
from cn_social_agent.tasks import TaskStatus
from cn_social_agent.tasks.engine import TaskError


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_task(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    alice = engine_factory()
    task = await alice.create_task("copywriter", "Alice 的私密选题", "内部内容")

    clear()
    as_user("u-bob")
    bob = engine_factory()

    rows = await bob.db.query("wb_nexus_tasks", filters={"id": f"eq.{task.id}"})
    assert rows == [], "Bob must not see Alice's row even when he knows the id"

    with pytest.raises(TaskError):
        await bob.get_task(task.id)

    listed = await bob.list_tasks()
    assert [t.id for t in listed] == []


@pytest.mark.asyncio
async def test_user_cannot_approve_another_users_task(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    alice = engine_factory()
    task = await alice.create_task("copywriter", "Alice 的任务", "内容")
    task = await alice.run_task(task.id)

    clear()
    as_user("u-bob")
    bob = engine_factory()
    with pytest.raises(TaskError):
        await bob.decide(task.id, "approve")

    clear()
    as_user("u-alice")
    again = engine_factory()
    assert (await again.get_task(task.id)).status is not TaskStatus.APPROVED


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_task(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    alice = engine_factory()
    task = await alice.create_task("copywriter", "不可删除", "内容")

    clear()
    as_user("u-bob")
    bob = engine_factory()
    await bob.delete_task(task.id)  # no-op: RLS restricts the delete to Bob's rows

    clear()
    as_user("u-alice")
    again = engine_factory()
    assert (await again.get_task(task.id)).id == task.id


@pytest.mark.asyncio
async def test_insert_is_stamped_with_caller_identity(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    engine = engine_factory()
    await engine.create_task("copywriter", "归属校验", "内容")

    rows = await engine.db.query("wb_nexus_tasks")
    assert rows, "RLS must let the owner read her own rows"
    assert {str(r["user_id"]) for r in rows} == {"u-alice"}


@pytest.mark.asyncio
async def test_forging_another_users_id_is_rejected(fake, registry, as_user, engine_factory):
    """RLS WITH CHECK, not application code, is what blocks this."""
    as_user("u-alice")
    db = TenantDB(fake)
    with pytest.raises(RlsViolation):
        await db.create(
            "wb_nexus_tasks",
            {"user_id": "u-bob", "expert_id": "copywriter", "title": "伪造", "brief": "x"},
        )


@pytest.mark.asyncio
async def test_anonymous_access_sees_nothing(fake, registry, as_user, engine_factory):
    """An unauthenticated caller is refused before it can reach the database."""
    as_user("u-alice")
    engine = engine_factory()
    await engine.create_task("copywriter", "有主的任务", "内容")

    clear()
    bind(TenantContext(user_id="", token=""))
    try:
        db = TenantDB(fake)
        with pytest.raises((RlsViolation, TenantError)):
            await db.create("wb_nexus_tasks", {"expert_id": "copywriter",
                                               "title": "匿名", "brief": "x"})
        with pytest.raises((RlsViolation, TenantError)):
            await db.query("wb_nexus_tasks")
    finally:
        clear()


@pytest.mark.asyncio
async def test_unfiltered_writes_are_refused_by_the_client(fake, registry, as_user, engine_factory):
    """Defence in depth: TenantDB refuses blanket updates/deletes outright."""
    as_user("u-alice")
    db = TenantDB(fake)
    with pytest.raises(ValueError, match="unfiltered update"):
        await db.update("wb_nexus_tasks", {}, {"status": "approved"})
    with pytest.raises(ValueError, match="unfiltered delete"):
        await db.delete("wb_nexus_tasks", {})


@pytest.mark.asyncio
async def test_admin_gateway_refuses_to_run_inside_a_tenant_request(
    fake, registry, as_user, engine_factory
):
    """The maintenance channel must not be reachable from request handling."""
    as_user("u-alice")
    admin = AdminGateway(fake)
    with pytest.raises(AdminError, match="bypass RLS"):
        await admin.exec_sql("SELECT 1;")


@pytest.mark.asyncio
async def test_task_lists_are_scoped_per_user(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    alice = engine_factory()
    await alice.create_task("copywriter", "A1", "内容")
    await alice.create_task("copywriter", "A2", "内容")

    clear()
    as_user("u-bob")
    bob = engine_factory()
    await bob.create_task("copywriter", "B1", "内容")

    bob_rows = await bob.list_tasks()
    assert len(bob_rows) == 1
    assert bob_rows[0].title == "B1"

    clear()
    as_user("u-alice")
    alice_rows = await alice.list_tasks()
    assert {t.title for t in alice_rows} == {"A1", "A2"}
