CREATE OR ALTER VIEW vd_subclass AS
SELECT
    i.pcid,
    pc.name AS pname,
    i.ccid,
    cc.name AS cname,
    cc.n_level,
    cc.[type],
    cc.name_path,
    cc.id_path
FROM
    inheritance i,
    class pc,
    class cc
WHERE
    pc.cid = i.pcid
    and cc.cid = i.ccid;
GO

CREATE OR ALTER VIEW vd_class_object AS
SELECT
    co.cid,
    c.name AS cname,
    c.[type] AS ctype, -- 修正拼字 cype -> ctype
    co.oid,
    o.oname AS oname,  -- 修正 name -> oname
    o.[type] AS otype,
    o.since
FROM
    co co,
    class c,
    object o
WHERE
    c.cid = co.cid
    and o.oid = co.oid;
GO

CREATE OR ALTER VIEW vd_orel AS
SELECT
    r.oid1,
    o1.oname AS from_object_name, -- 修正 name -> oname
    o1.[type] AS from_object_type,
    r.rel_type,
    r.oid2,
    o2.oname AS to_object_name,   -- 修正 name -> oname
    o2.[type] AS to_object_type,
    r.since
FROM
    orel r,
    object o1,
    object o2
WHERE
    r.oid1 = o1.oid
    and r.oid2 = o2.oid;
GO

CREATE OR ALTER VIEW vd_video AS
SELECT TOP (30)
    o.oname, -- 修正 name -> oname
    v.channel_title
FROM object o
INNER JOIN video v ON o.oid = v.vid
WHERE o.[type] = 4 -- 4 代表影片 (若原本定義為 4 的話)
  AND o.data_byte IS NULL
ORDER BY o.since ASC;
GO
