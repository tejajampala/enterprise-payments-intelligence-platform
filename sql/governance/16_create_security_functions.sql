CREATE OR REPLACE FUNCTION payments_dev.governance.mask_string(
    value STRING
)
RETURNS STRING
RETURN
    CASE
        WHEN value IS NULL THEN NULL
        ELSE '***MASKED***'
    END;


CREATE OR REPLACE FUNCTION payments_dev.governance.mask_email(
    value STRING
)
RETURNS STRING
RETURN
    CASE
        WHEN value IS NULL THEN NULL
        WHEN instr(value, '@') > 1
            THEN concat('***@', element_at(split(value, '@'), 2))
        ELSE '***MASKED***'
    END;


CREATE OR REPLACE FUNCTION payments_dev.governance.mask_date_of_birth(
    value DATE
)
RETURNS DATE
RETURN
    CASE
        WHEN value IS NULL THEN NULL
        ELSE make_date(year(value), 1, 1)
    END;


CREATE OR REPLACE FUNCTION payments_dev.governance.allow_au_country(
    country STRING
)
RETURNS BOOLEAN
RETURN
    upper(country) = 'AU';