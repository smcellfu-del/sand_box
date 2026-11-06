
create DATABASE Manual_import

use [Manual_import];
go


create table dbo.[object] (
    oid int identity(1,1) not null,
    oname nvarchar(500),
    [type] int not null
        constraint df_object_type
        default 0,
    description nvarchar(500) null,
    since datetime2(3) not null
        constraint df_object_since
        default sysdatetime(),
    last_modified_dt datetime2(3) not null
        constraint df_object_last_modified
        default sysdatetime(),
    data_byte binary(1) null,
    n_click int not null
        constraint df_object_n_click
        default 0,
    constraint pk_object
        primary key clustered (oid)
);r
go


create table dbo.artist (
    aid int not null,
    artist_type nvarchar(50) null,
    gender nvarchar(20) null,
    country nvarchar(10) null,
    begin_date nvarchar(20) null,
    end_date nvarchar(20) null,
    is_ended bit null,
    constraint pk_artist
        primary key clustered (aid),
    constraint fk_artist_object
        foreign key (aid)
        references dbo.[object](oid)
        on delete cascade
);
go


create table dbo.song (
    sid int not null,
    img_path nvarchar(500) null,
    first_release_date nvarchar(20) null,
    duration_ms int null,
    constraint pk_song
        primary key clustered (sid),
    constraint fk_song_object
        foreign key (sid)
        references dbo.[object](oid)
        on delete cascade,
    constraint chk_song_duration
        check (
            duration_ms is null
            or duration_ms >= 0
        )
);
go


create table dbo.album (
    alid int not null,
    img_path nvarchar(500) null,
    album_type nvarchar(50) null,

    constraint pk_album
        primary key clustered (alid),
    constraint fk_album_object
        foreign key (alid)
        references dbo.[object](oid)
        on delete cascade,
    constraint chk_album_secondary_types_json
        check (
            secondary_types_json is null
            or isjson(secondary_types_json) = 1
        )
);
go


create table dbo.video (
    vid int not null,
    ytid nvarchar(50) not null,
    yt_url as (
        N'https://www.youtube.com/watch?v=' + ytid
    ) persisted,
    channel_id nvarchar(100) null,
    channel_title nvarchar(255) null,
    duration_ms int null,
    view_count bigint not null
        constraint df_video_view_count
        default 0,
    img_path nvarchar(500) null,
    published_at datetime2(3) null,
    is_ended bit not null
        constraint df_video_is_ended
        default 0,
    last_sync_dt datetime2(3) not null
        constraint df_video_last_sync
        default sysdatetime(),
    constraint pk_video
        primary key clustered (vid),
    constraint uq_video_ytid
        unique (ytid),
    constraint fk_video_object
        foreign key (vid)
        references dbo.[object](oid)
        on delete cascade,
    constraint chk_video_duration
        check (
            duration_ms is null
            or duration_ms >= 0
        ),
    constraint chk_video_view_count
        check (view_count >= 0)
);
go


create table dbo.tag (
    tid int not null,
    tag_type varchar(30) not null,
    constraint pk_tag
        primary key clustered (tid),

    constraint fk_tag_object
        foreign key (tid)
        references dbo.[object](oid)
        on delete cascade
);
go


create table dbo.orel (
    orid bigint identity(1,1) not null,
    oid1 int not null,
    oid2 int not null,
    rel_type nvarchar(100) not null,
    since nvarchar(255) null,
    rank int null,
    since datetime2(3) not null
        constraint df_orel_since
        default sysdatetime(),
    last_modified_dt datetime2(3) not null
        constraint df_orel_last_modified
        default sysdatetime(),
    constraint pk_orel
        primary key clustered (orid),
    constraint fk_orel_oid1
        foreign key (oid1)
        references dbo.[object](oid),
    constraint fk_orel_oid2
        foreign key (oid2) references dbo.[object](oid),
    constraint fk_orel_source
        foreign key (source_id)
        references dbo.object_source(source_id)
        on delete set null,

    constraint chk_orel_attributes_json
        check (
            attributes_json is null
            or isjson(attributes_json) = 1
        )
);
go

create table co (
    cid int not null,
    oid int not null,
    rank smallint null,
    mg tinyint null,
	since datetime2 not null default sysdatetime(),
    constraint pk_co primary key clustered (cid, oid , since),
    constraint fk_co_cid foreign key (cid) references class(cid),
    constraint fk_co_oid foreign key (oid) references object(oid)
);
go


create table class (
    cid int identity(1,1) primary key,
    name nvarchar(255) not null,
    enf_name nvarchar(255) null,
    des nvarchar(500) null,
    since datetime2 not null default sysdatetime(),
    name_path nvarchar(1000) null,
    id_path nvarchar(1000) null,
    n_level int not null default 0,
    type int not null default 0,
    owner_mid int null,

);

create table inheritance (
    pcid int not null,
    ccid int not null,
    rank int not null default 0,
    primary key (pcid, ccid),
    constraint fk_inheritance_pcid foreign key (pcid) references class(cid),
    constraint fk_inheritance_ccid foreign key (ccid) references class(cid)
);
ALTER TABLE dbo.class
ADD source_id NVARCHAR(100) NULL;



create table dbo.subtitle (
    suid bigint identity(1,1) not null,
    vid int not null,
    subtitle nvarchar(max) not null,
    start_time decimal(12,3) not null,
    end_time decimal(12,3) not null,
    [type] nvarchar(20) null,
    lang nvarchar(20) null,
    rank int null,

    since datetime2(3) not null
        constraint df_subtitle_since
        default sysdatetime(),

    last_modified_dt datetime2(3) not null
        constraint df_subtitle_last_modified
        default sysdatetime(),

    constraint pk_subtitle
        primary key clustered (suid),

    constraint fk_subtitle_video
        foreign key (vid)
        references dbo.video(vid)
        on delete cascade,

    constraint chk_subtitle_time
        check (
            start_time >= 0
            and end_time >= start_time
        )
);
go

create index ix_subtitle_vid_time
on dbo.subtitle (vid, start_time, end_time);
go