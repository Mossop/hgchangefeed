CREATE INDEX `website_path_path` ON `website_path` (`path`(200));
CREATE INDEX `website_path_name` ON `website_path` (`name`(200));
CREATE INDEX `website_path_repository` ON `website_path` (`repository_id`);
ALTER TABLE `website_path` ADD CONSTRAINT UNIQUE (`repository_id`, `path`(200));
ALTER TABLE `website_path` ADD CONSTRAINT UNIQUE (`repository_id`, `parent_id`, `name`);
