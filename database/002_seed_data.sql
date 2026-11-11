BEGIN;

INSERT INTO roles (id, code, name, description)
VALUES
    (1, 'admin', 'Administrador', 'Gestiona usuarios, catálogo, servicios y reportes.'),
    (2, 'user', 'Usuario', 'Consulta el catálogo y utiliza los servicios de inteligencia artificial.')
ON CONFLICT (id) DO NOTHING;

SELECT setval(
    pg_get_serial_sequence('roles', 'id'),
    greatest((SELECT max(id) FROM roles), 1),
    TRUE
);

-- Credenciales exclusivas de demostración local:
-- admin@alejandria.local  / Cambiar123!
-- lector@alejandria.local / Cambiar123!
-- pgcrypto genera hashes bcrypt; la API deberá aceptar bcrypt para usuarios semilla y
-- usar Argon2 para las contraseñas creadas o cambiadas desde la aplicación.
INSERT INTO users (
    id,
    role_id,
    email,
    display_name,
    password_hash,
    monthly_token_limit
)
VALUES
    (
        '10000000-0000-0000-0000-000000000001',
        1,
        'admin@alejandria.local',
        'Administrador de Alejandría',
        crypt('Cambiar123!', gen_salt('bf', 12)),
        500000
    ),
    (
        '10000000-0000-0000-0000-000000000002',
        2,
        'lector@alejandria.local',
        'Lector de demostración',
        crypt('Cambiar123!', gen_salt('bf', 12)),
        100000
    )
ON CONFLICT (email) DO NOTHING;

INSERT INTO publishers (id, name, country_code)
VALUES
    ('20000000-0000-0000-0000-000000000001', 'Editorial de demostración', 'GT')
ON CONFLICT (name) DO NOTHING;

INSERT INTO authors (
    id,
    full_name,
    biography,
    birth_date,
    death_date,
    country_code
)
VALUES
    (
        '30000000-0000-0000-0000-000000000001',
        'Miguel de Cervantes Saavedra',
        'Novelista, poeta y dramaturgo español, autor de Don Quijote de la Mancha.',
        '1547-09-29',
        '1616-04-22',
        'ES'
    ),
    (
        '30000000-0000-0000-0000-000000000002',
        'Jane Austen',
        'Novelista inglesa reconocida por sus obras sobre la sociedad y la vida doméstica.',
        '1775-12-16',
        '1817-07-18',
        'GB'
    ),
    (
        '30000000-0000-0000-0000-000000000003',
        'Mary Shelley',
        'Escritora inglesa conocida principalmente por la novela Frankenstein.',
        '1797-08-30',
        '1851-02-01',
        'GB'
    ),
    (
        '30000000-0000-0000-0000-000000000004',
        'Franz Kafka',
        'Escritor de lengua alemana cuya obra explora la alienación y la burocracia.',
        '1883-07-03',
        '1924-06-03',
        'CZ'
    ),
    (
        '30000000-0000-0000-0000-000000000005',
        'José Martí',
        'Poeta, ensayista y pensador cubano, figura central del modernismo hispanoamericano.',
        '1853-01-28',
        '1895-05-19',
        'CU'
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO genres (id, name, description)
VALUES
    (1, 'Novela', 'Narrativa extensa de ficción.'),
    (2, 'Clásicos', 'Obras de relevancia histórica y literaria.'),
    (3, 'Ciencia ficción', 'Ficción basada en posibilidades científicas o tecnológicas.'),
    (4, 'Romance', 'Narrativa centrada en relaciones afectivas.'),
    (5, 'Terror gótico', 'Ficción de atmósfera oscura, misterio y elementos sobrenaturales.'),
    (6, 'Filosofía', 'Obras orientadas a problemas y reflexiones filosóficas.'),
    (7, 'Poesía', 'Composiciones literarias poéticas.')
ON CONFLICT (id) DO NOTHING;

SELECT setval(
    pg_get_serial_sequence('genres', 'id'),
    greatest((SELECT max(id) FROM genres), 1),
    TRUE
);

INSERT INTO books (
    id,
    publisher_id,
    title,
    synopsis,
    publication_year,
    language_code,
    page_count
)
VALUES
    (
        '40000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001',
        'Don Quijote de la Mancha',
        'Un hidalgo aficionado a los libros de caballería decide convertirse en caballero andante.',
        1605,
        'es',
        863
    ),
    (
        '40000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000001',
        'Orgullo y prejuicio',
        'Elizabeth Bennet confronta las normas sociales, los prejuicios y sus propios sentimientos.',
        1813,
        'es',
        432
    ),
    (
        '40000000-0000-0000-0000-000000000003',
        '20000000-0000-0000-0000-000000000001',
        'Frankenstein',
        'Víctor Frankenstein crea un ser vivo y debe enfrentar las consecuencias de su experimento.',
        1818,
        'es',
        280
    ),
    (
        '40000000-0000-0000-0000-000000000004',
        '20000000-0000-0000-0000-000000000001',
        'La metamorfosis',
        'Gregor Samsa despierta convertido en un insecto y su familia reacciona ante la transformación.',
        1915,
        'es',
        128
    ),
    (
        '40000000-0000-0000-0000-000000000005',
        '20000000-0000-0000-0000-000000000001',
        'Versos sencillos',
        'Colección poética que aborda la identidad, la amistad, la libertad y la naturaleza.',
        1891,
        'es',
        96
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO book_authors (book_id, author_id, author_order, contribution)
VALUES
    ('40000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 1, 'author'),
    ('40000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002', 1, 'author'),
    ('40000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003', 1, 'author'),
    ('40000000-0000-0000-0000-000000000004', '30000000-0000-0000-0000-000000000004', 1, 'author'),
    ('40000000-0000-0000-0000-000000000005', '30000000-0000-0000-0000-000000000005', 1, 'author')
ON CONFLICT DO NOTHING;

INSERT INTO book_genres (book_id, genre_id)
VALUES
    ('40000000-0000-0000-0000-000000000001', 1),
    ('40000000-0000-0000-0000-000000000001', 2),
    ('40000000-0000-0000-0000-000000000002', 1),
    ('40000000-0000-0000-0000-000000000002', 2),
    ('40000000-0000-0000-0000-000000000002', 4),
    ('40000000-0000-0000-0000-000000000003', 1),
    ('40000000-0000-0000-0000-000000000003', 2),
    ('40000000-0000-0000-0000-000000000003', 3),
    ('40000000-0000-0000-0000-000000000003', 5),
    ('40000000-0000-0000-0000-000000000004', 1),
    ('40000000-0000-0000-0000-000000000004', 2),
    ('40000000-0000-0000-0000-000000000004', 6),
    ('40000000-0000-0000-0000-000000000005', 2),
    ('40000000-0000-0000-0000-000000000005', 7)
ON CONFLICT DO NOTHING;

COMMIT;
