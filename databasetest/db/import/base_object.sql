USE [Manual_import];
GO

-- ==========================================
-- 1. 插入 Artist (ヨルシカ)
-- ==========================================
INSERT INTO dbo.[object] (oname, [type], data_byte)
VALUES (N'ヨルシカ', 1, 0x00);

DECLARE @artist_oid INT = SCOPE_IDENTITY();

INSERT INTO dbo.artist (aid, artist_type, country)
VALUES (@artist_oid, N'Group', N'JP');


-- ==========================================
-- 2. 插入 Album (幻燈)
-- ==========================================
INSERT INTO dbo.[object] (oname, [type], data_byte)
VALUES (N'幻燈', 2, 0x00);

DECLARE @album_oid INT = SCOPE_IDENTITY();

INSERT INTO dbo.album (alid, album_type)
VALUES (@album_oid, N'Album');


-- ==========================================
-- 3. 批次插入 Song (多首歌曲)
-- ==========================================
-- 這裡宣告一個暫存表來收集歌曲的 oid 與名稱，方便後續建立關聯
DECLARE @InsertedSongs TABLE (sid INT, song_name NVARCHAR(500));

-- 逐一插入歌曲到 object 並寫入 song 表格
-- (註: data_byte 在你的表格定義中型態是 binary(1)，0x00 代表 1 byte 的 0)
DECLARE @songs TABLE (sname NVARCHAR(500));
INSERT INTO @songs (sname) VALUES
(N'夏の肖像'), (N'都落ち'), (N'ブレーメン'), (N'チノカテ'), (N'雪国'),
(N'月に吠える'), (N'451'), (N'パドドゥ'), (N'又三郎'), (N'靴の花火'),
(N'老人と海'), (N'さよならモルテン'), (N'いさな'), (N'左右盲'), (N'アルジャーノン'),
(N'第一夜'), (N'第二夜'), (N'第三夜'), (N'第四夜'), (N'第五夜'),
(N'第六夜'), (N'第七夜'), (N'第八夜'), (N'第九夜'), (N'第十夜');

-- 迴圈批次建立 Object 與 Song
DECLARE @curr_sname NVARCHAR(500);
DECLARE song_cursor CURSOR FOR SELECT sname FROM @songs;
OPEN song_cursor;
FETCH NEXT FROM song_cursor INTO @curr_sname;

WHILE @@FETCH_STATUS = 0
BEGIN
    INSERT INTO dbo.[object] (oname, [type], data_byte)
    VALUES (@curr_sname, 3, 0x00);

    DECLARE @song_oid INT = SCOPE_IDENTITY();

    INSERT INTO dbo.song (sid)
    VALUES (@song_oid);

    INSERT INTO @InsertedSongs (sid, song_name)
    VALUES (@song_oid, @curr_sname);

    FETCH NEXT FROM song_cursor INTO @curr_sname;
END
CLOSE song_cursor;
DEALLOCATE song_cursor;


-- ==========================================
-- 4. 建立 Orel 關係 (orel)
-- ==========================================
-- 4.1 藝人 (Artist) -> 專輯 (Album)
INSERT INTO dbo.orel (oid1, oid2, rel_type)
VALUES (@artist_oid, @album_oid, N'artist_album');

-- 4.2 藝人 (Artist) -> 所有歌曲 (Song)
INSERT INTO dbo.orel (oid1, oid2, rel_type)
SELECT @artist_oid, sid, N'artist_song'
FROM @InsertedSongs;

-- 4.3 專輯 (Album) -> 所有歌曲 (Song)
INSERT INTO dbo.orel (oid1, oid2, rel_type)
SELECT @album_oid, sid, N'album_song'
FROM @InsertedSongs;
GO





DECLARE @VideoData TABLE (
    row_idx INT,
    ytid NVARCHAR(50),
    title NVARCHAR(500),
    duration_ms INT
);

-- 批次塞入你提供的 25 筆資料
INSERT INTO @VideoData (row_idx, ytid, title, duration_ms) VALUES
(0, N'k480n7NBXP4', N'Portrait of Summer', 326000),
(1, N'pHdJmDFYqTU', N'ヨルシカ - 都落ち（OFFICIAL VIDEO）', 265000),
(2, N'oy6MDr6I6rM', N'ヨルシカ - ブレーメン（OFFICIAL VIDEO）', 280000),
(3, N'Fq55MMfHoJg', N'ヨルシカ - チノカテ（OFFICIAL VIDEO）', 255000),
(4, N'5bpHW3ToFlQ', N'Snow Country', 288000),
(5, N'wCN9WliV-ew', N'ヨルシカ - 月に吠える（OFFICIAL VIDEO）', 267000),
(6, N'RmYdZZLOYA8', N'ヨルシカ - 451（OFFICIAL VIDEO）', 210000),
(7, N'0JU__LPuaPQ', N'Pas de Deux', 263000),
(8, N'siNFnlqtd8M', N'ヨルシカ - 又三郎（OFFICIAL VIDEO）', 231000),
(9, N'Q-s6lSQK_I4', N'Fireworks of shoes (Re-Recording)', 306000),
(10, N't2MjHjP2HdE', N'The Old Man and the Sea', 256000),
(11, N'MP4iEK_btKU', N'Goodbye Molten', 296000),
(12, N'F_cmjdKbWnU', N'Whale', 265000),
(13, N'1IlTeOMCNJU', N'ヨルシカ - 左右盲（OFFICIAL VIDEO）', 272000),
(14, N'_9_rUFrgLI8', N'ヨルシカ - アルジャーノン（OFFICIAL VIDEO）', 261000),
(15, N'-R8UiY_44Y0', N'ヨルシカ - 第一夜（OFFICIAL VIDEO）', 270000),
(16, N'NXqSJmkSn4s', N'The Second Night', 254000),
(17, N'tXjKQZ_lWIg', N'The Third Night', 232000),
(18, N'jki_pUPLbDs', N'The Fourth Night', 203000),
(19, N'FcfJEPvCakg', N'The Fifth Night', 221000),
(20, N'B7O-NLqgWjo', N'The Sixth Night', 147000),
(21, N'cRHIpTcJWW8', N'The Seventh Night', 194000),
(22, N'o2-24VoEWGU', N'The Eighth Night', 182000),
(23, N'e3dwxV2UDik', N'The Ninth Night', 144000),
(24, N'PUz3ZtvEG5M', N'The Tenth Night', 229000);

-- 2. 逐筆建立 Object 與 Video，並對應到原本順序相同的 Song
DECLARE @idx INT, @ytid NVARCHAR(50), @title NVARCHAR(500), @dur INT;
DECLARE @video_oid INT;

-- 宣告一個排序用的游標依照 row_idx 確保絕對順序
DECLARE cur CURSOR FOR
    SELECT row_idx, ytid, title, duration_ms
    FROM @VideoData
    ORDER BY row_idx ASC;

OPEN cur;
FETCH NEXT FROM cur INTO @idx, @ytid, @title, @dur;

WHILE @@FETCH_STATUS = 0
BEGIN
    -- 2.1 建立 Video 的 Object
    INSERT INTO dbo.[object] (oname, [type], data_byte)
    VALUES (@title, 4, 0x00); -- 假設 type 4 代表影片

    SET @video_oid = SCOPE_IDENTITY();

    -- 2.2 寫入 video 表格
    INSERT INTO dbo.video (vid, ytid, duration_ms)
    VALUES (@video_oid, @ytid, @dur);

    -- 2.3 找出對應順序的 Song oid (透過 Row_Number 確保 1 對 1 順序對應)
    WITH RankedSongs AS (
        SELECT oid, ROW_NUMBER() OVER (ORDER BY oid ASC) AS rn
        FROM dbo.song s
        JOIN dbo.[object] o ON s.sid = o.oid
    )
    -- 建立 orel 關聯：Song (oid1) -> Video (oid2) 或反之
    INSERT INTO dbo.orel (oid1, oid2, rel_type, [rank])
    SELECT oid, @video_oid, N'song_video', @idx
    FROM RankedSongs
    WHERE rn = (@idx + 1); -- 因為 row_idx 從 0 開始，rn 從 1 開始

    FETCH NEXT FROM cur INTO @idx, @ytid, @title, @dur;
END

CLOSE cur;
DEALLOCATE cur;
GO
