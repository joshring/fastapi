
create table if not exists users (
	id 			serial primary key,
	username 	varchar not null,
	email 		varchar not null,
	unique(username, email)
);

create table if not exists events (
	id 			serial primary key,
	user_id 	int references users(id) on delete cascade,
	t 			bigint not null, -- time in seconds, presumably unix time since epoch
	amount 		numeric(12,2) not null,
	event_type 	varchar not null,
	alert 		bool not null,
	alert_codes jsonb,
	unique(user_id, t)
);

-- Seed the users table with a user for testing purposes
insert into users(username, email)
values
	('John Doe', 'john.doe@example.com'),
	('Mary Doe', 'mary.doe@example.com');
