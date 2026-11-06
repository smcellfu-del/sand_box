-- 1. 藝人 (Artist) 對應到「藝人」分類
INSERT INTO dbo.co (cid, oid, [rank], mg)
SELECT c.cid, a.aid, 0, 0
FROM dbo.artist a
CROSS JOIN dbo.class c
WHERE c.name = N'藝人' AND c.n_level = 2;

-- 2. 專輯 (Album) 對應到「專輯」分類
INSERT INTO dbo.co (cid, oid, [rank], mg)
SELECT c.cid, al.alid, 0, 0
FROM dbo.album al
CROSS JOIN dbo.class c
WHERE c.name = N'專輯' AND c.n_level = 2;

-- 3. 歌曲 (Song) 對應到「歌曲」分類
INSERT INTO dbo.co (cid, oid, [rank], mg)
SELECT c.cid, s.sid, 0, 0
FROM dbo.song s
CROSS JOIN dbo.class c
WHERE c.name = N'歌曲' AND c.n_level = 2;

-- 4. 影片 (Video) 對應到「影片」分類
INSERT INTO dbo.co (cid, oid, [rank], mg)
SELECT c.cid, v.vid, 0, 0
FROM dbo.video v
CROSS JOIN dbo.class c
WHERE c.name = N'影片' AND c.n_level = 2;

-- ==========================================
-- 5. Tag 關聯 (j-pop)
-- ==========================================

-- 5.1 藝人的 Tag (j-pop) 對應到藝人物件
INSERT INTO dbo.co (cid, oid, [rank], mg)
SELECT c.cid, a.aid, 0, 0
FROM dbo.artist a
CROSS JOIN dbo.class c
WHERE c.name = N'j-pop' AND c.name_path LIKE N'%首頁\藝人\Tag\j-pop%';

-- 5.2 專輯的 Tag (j-pop) 對應到專輯物件
INSERT INTO dbo.co (cid, oid, [rank], mg)
SELECT c.cid, al.alid, 0, 0
FROM dbo.album al
CROSS JOIN dbo.class c
WHERE c.name = N'j-pop' AND c.name_path LIKE N'%首頁\專輯\Tag\j-pop%';

-- 5.3 歌曲的 Tag (j-pop) 對應到所有歌曲物件
INSERT INTO dbo.co (cid, oid, [rank], mg)
SELECT c.cid, s.sid, 0, 0
FROM dbo.song s
CROSS JOIN dbo.class c
WHERE c.name = N'j-pop' AND c.name_path LIKE N'%首頁\歌曲\Tag\j-pop%';
GO
