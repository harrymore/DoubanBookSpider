DROP TABLE IF EXISTS `tag_info`;
CREATE TABLE `tag_info` (
	`id` INT(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
	`name` VARCHAR(30) NOT NULL COMMENT '标签名字',
	`page` SMALLINT(3) NOT NULL DEFAULT '0' COMMENT '当前页数，对应请求中的start值',
	`is_end` TINYINT(1) NOT NULL DEFAULT '0' COMMENT '是否完成，0：未完成，1：已完成',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='标签信息';

DROP TABLE IF EXISTS `book_info`;
CREATE TABLE `book_info` (
	`id` INT(11) NOT NULL COMMENT '书本在网站唯一id',
	`book_name` VARCHAR(200) DEFAULT NULL COMMENT '书名',
	`author` VARCHAR(100) DEFAULT NULL COMMENT '作者',
	`publisher` VARCHAR(200) DEFAULT NULL COMMENT '出版社',
	`translator` VARCHAR(100) DEFAULT NULL COMMENT '译者',
	`publish_date` VARCHAR(100) DEFAULT NULL COMMENT '出版年',
	`page_num` INT(6) DEFAULT '0' COMMENT '页数',
	`isbn` VARCHAR(20) DEFAULT NULL COMMENT '书号',
	`score` FLOAT(3,1) DEFAULT '0.0' COMMENT '评分',
	`rating_num` INT(11) DEFAULT '0' COMMENT '评分人数',
  	PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='书本信息';

