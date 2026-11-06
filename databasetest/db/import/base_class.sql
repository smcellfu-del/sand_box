USE [Manual_import];
GO

-- 1. 插入第一層：首頁 (cid = 1)
INSERT INTO dbo.class (name, n_level, name_path, id_path, [type])
VALUES (N'首頁', 1, N'首頁', N'1', 0);--type 目前還沒想清楚

-- 2. 插入第二層：影片、藝人、歌曲、專輯 (cid = 2, 3, 4, 5)
INSERT INTO dbo.class (name, n_level, name_path, id_path, [type]) VALUES
(N'影片', 2, N'首頁\影片', N'1\2', 0), --type 目前還沒想清楚
(N'藝人', 2, N'首頁\藝人', N'1\3', 0),
(N'歌曲', 2, N'首頁\歌曲', N'1\4', 0),
(N'專輯', 2, N'首頁\專輯', N'1\5', 0);

-- 3. 建立繼承關係 (pcid = 父層 cid, ccid = 子層 cid)
-- 首頁(1) 是 影片(2)、藝人(3)、歌曲(4)、專輯(5) 的父層
INSERT INTO dbo.inheritance (pcid, ccid, [rank]) VALUES
(1, 2, 0),
(1, 3, 0),
(1, 4, 0),
(1, 5, 0);

-- 4. 插入第三層：Tag（藝人、歌曲、專輯都可以有 Tag）
-- 假設分別掛在藝人(3)、歌曲(4)、專輯(5)底下
INSERT INTO dbo.class (name, n_level, name_path, id_path, [type]) VALUES
(N'Tag', 3, N'首頁\藝人\Tag', N'1\3\6', 0),
(N'Tag', 3, N'首頁\歌曲\Tag', N'1\4\7', 0),
(N'Tag', 3, N'首頁\專輯\Tag', N'1\5\8', 0);

-- 建立 Tag 的繼承關係
INSERT INTO dbo.inheritance (pcid, ccid, [rank]) VALUES
(3, 6, 0), -- 藝人 -> 藝人的 Tag
(4, 7, 0), -- 歌曲 -> 歌曲的 Tag
(5, 8, 0); -- 專輯 -> 專輯的 Tag

-- 5. 插入第四層：各領域的 j-pop Tag
INSERT INTO dbo.class (name, n_level, name_path, id_path, [type]) VALUES
(N'j-pop', 4, N'首頁\藝人\Tag\j-pop', N'1\3\6\9', 0),
(N'j-pop', 4, N'首頁\歌曲\Tag\j-pop', N'1\4\7\10', 0),
(N'j-pop', 4, N'首頁\專輯\Tag\j-pop', N'1\5\8\11', 0);

-- 建立 j-pop 的繼承關係
INSERT INTO dbo.inheritance (pcid, ccid, [rank]) VALUES
(6, 9, 0),   -- 藝人Tag -> j-pop
(7, 10, 0),  -- 歌曲Tag -> j-pop
(8, 11, 0);  -- 專輯Tag -> j-pop
GO

INSERT INTO dbo.class (name, n_level, name_path, id_path, [type], source_id)
VALUES (
    N'Magic Lantern',
    4,
    N'首頁\使用者\上傳的播放清單\Magic Lantern',
    N'1\12\13\14',
    0,
    N'OLAK5uy_n3YRy2_ZenF9_ElL2ysKuPJ_U9kIv-vOE' -- 這裡放 YouTube 原始 ID
);


-- 2. 插入「使用者」層級 (n_level = 2)
INSERT INTO dbo.class (name, n_level, name_path, id_path, [type])
VALUES (N'使用者', 2, N'首頁\使用者', N'1\2', 0);

-- 取得剛剛插入的「使用者」cid (通常是 2，若前面有資料則動態抓取)
DECLARE @user_cid INT = SCOPE_IDENTITY();

-- 建立 首頁(cid=1) -> 使用者 的繼承關係
INSERT INTO dbo.inheritance (pcid, ccid, [rank])
VALUES (1, @user_cid, 0);


-- 3. 插入「上傳的播放清單」層級 (n_level = 3)
INSERT INTO dbo.class (name, n_level, name_path, id_path, [type])
VALUES (N'上傳的播放清單', 3, N'首頁\使用者\上傳的播放清單', CONCAT(N'1\', @user_cid, N'\3'), 0);

DECLARE @playlist_folder_cid INT = SCOPE_IDENTITY();

-- 建立 使用者 -> 上傳的播放清單 的繼承關係
INSERT INTO dbo.inheritance (pcid, ccid, [rank])
VALUES (@user_cid, @playlist_folder_cid, 0);
GO
