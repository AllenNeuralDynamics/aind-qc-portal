"""OpenAPI documentation for the Panel server's custom HTTP endpoints."""

from tornado.web import RequestHandler

from aind_qc_portal import __version__


def _ref(name):
    """Reference a shared request or response schema."""
    return {"$ref": f"#/components/schemas/{name}"}


def _object(properties, required=(), **extra):
    """Describe a JSON object with its required fields."""
    schema = {"type": "object", "properties": properties, **extra}
    if required:
        schema["required"] = list(required)
    return schema


def _body(schema):
    """Describe a required JSON request body."""
    return {"required": True, "content": {"application/json": {"schema": schema}}}


def _parameter(name, location="query", required=False, **schema):
    """Describe a query or path parameter."""
    return {"name": name, "in": location, "required": required, "schema": {"type": "string", **schema}}


def _operation(summary, tag, response, *, status="200", errors=(), security=(), **extra):
    """Describe an operation and its success and error responses."""
    responses = {status: {"description": "Success", "content": {"application/json": {"schema": response}}}}
    for code in errors:
        responses[str(code)] = {
            "description": {
                400: "Invalid request or no changes",
                401: "Authentication required",
                403: "Origin or permission denied",
                404: "Record or proposal not found",
                409: "Stale record, proposal conflict, or mismatched write target",
                422: "QC schema validation failed",
                502: "Upstream service unavailable",
                503: "QC API disabled or unavailable",
            }.get(code, "Request failed"),
            "content": {"application/json": {"schema": _ref("Error")}},
        }
    return {"summary": summary, "tags": [tag], "security": list(security), "responses": responses, **extra}


def openapi_spec():
    """Return the public API contract without deployment secrets or live data."""
    string = {"type": "string"}
    arbitrary = {"type": "object", "additionalProperties": True}
    bearer = [{"EntraBearer": []}]
    cookie = [{"MetadataSession": []}]
    origin_note = (
        "Writes require an Origin header matching QC_API_ALLOWED_ORIGINS and an Entra ID identity token. "
        "Try it out uses this page's origin, which must be allowed by the deployment."
    )
    proposal_response = _object({"proposal": arbitrary})
    schemas = {
        "Error": _object({"status": string, "error": string, "detail": string}, ("status", "error")),
        "MetricChange": _object(
            {
                "metric_name": {"type": "string", "minLength": 1},
                "value": {},
                "status": {"type": "string", "enum": ["Pass", "Fail", "Pending"]},
                "delete_curation_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 1,
                    "uniqueItems": True,
                },
            },
            ("metric_name",),
            additionalProperties=False,
            anyOf=[{"required": [key]} for key in ("value", "status", "delete_curation_indices")],
        ),
        "NewMetric": _object(
            {
                "name": {"type": "string", "minLength": 1},
                "modality": arbitrary,
                "stage": string,
                "value": {},
                "description": string,
                "reference": {"type": "string", "nullable": True},
                "tags": {"type": "object", "additionalProperties": string},
            },
            ("name", "value"),
            additionalProperties=False,
            description="Plain QC metric validated against the QC schema; the server assigns Pending status and evaluator.",
        ),
        "QcSubmit": _object(
            {
                "record_id": {"type": "string", "minLength": 1, "maxLength": 256},
                "expected_qc_hash": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                    "description": "SHA-256 of canonical QC JSON using the JCS-SHA256-v1 browser/server contract.",
                },
                "changes": {"type": "array", "items": _ref("MetricChange")},
                "notes": string,
                "add_metrics": {"type": "array", "items": _ref("NewMetric")},
                "allow_tag_failures": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "pattern": r"\S"},
                    "description": "Tag values to merge into existing allowances, preserving existing values and removing duplicates.",
                },
            },
            ("record_id", "expected_qc_hash", "changes"),
            additionalProperties=False,
            description="At least one effective change is required. Maximum request body: 256 KiB.",
        ),
        "QcApplied": _object(
            {
                "status": {"type": "string", "enum": ["applied"]},
                "record_id": string,
                "asset_name": string,
                "actor": string,
                "changed_metrics": {"type": "integer"},
                "added_metrics": {"type": "integer"},
                "docdb_status": {"type": "integer"},
            }
        ),
        "CreateProposal": _object(
            {
                "version": {"type": "string", "enum": ["v1", "v2"]},
                "id": string,
                "body": arbitrary,
                "note": string,
                "supersedes": string,
            },
            ("version", "body"),
            description="Supply id or body._id; body._id must match the requested record.",
        ),
    }
    proposal_id = _parameter("proposal_id", "path", True)
    paths = {
        "/api/qc/submit": {
            "post": _operation(
                "Submit QC edits",
                "QC",
                _ref("QcApplied"),
                security=bearer,
                errors=(400, 401, 403, 404, 409, 422, 502, 503),
                description=origin_note,
                requestBody=_body(_ref("QcSubmit")),
            )
        },
        "/metadata/proposals": {
            "get": _operation(
                "List metadata proposals",
                "Metadata proposals",
                _object(
                    {
                        "proposals": {"type": "array", "items": arbitrary},
                    }
                ),
                errors=(400, 502),
                parameters=[
                    _parameter("status", default="open", description="Comma-separated statuses or all."),
                    _parameter("version", enum=["v1", "v2"]),
                    _parameter("id"),
                    _parameter("summary", type="boolean", default=False),
                ],
            ),
            "post": _operation(
                "Create metadata proposal",
                "Metadata proposals",
                proposal_response,
                status="201",
                errors=(400, 401, 403, 404, 409, 502, 503),
                security=bearer,
                description=origin_note,
                requestBody=_body(_ref("CreateProposal")),
            ),
        },
        "/metadata/proposals/{proposal_id}": {
            "get": _operation(
                "Read metadata proposal",
                "Metadata proposals",
                proposal_response,
                errors=(404, 502),
                parameters=[proposal_id],
            ),
            "delete": _operation(
                "Withdraw own open proposal",
                "Metadata proposals",
                proposal_response,
                errors=(401, 403, 404, 409, 502, 503),
                security=bearer,
                description=origin_note,
                parameters=[proposal_id],
            ),
        },
        "/metadata/proposals/{proposal_id}/approve": {
            "post": _operation(
                "Approve and apply metadata proposal",
                "Metadata proposals",
                _object(
                    {
                        "status": string,
                        "proposal": arbitrary,
                    }
                ),
                errors=(400, 401, 403, 404, 409, 502, 503),
                security=bearer,
                parameters=[proposal_id],
                description=origin_note
                + " Reviewer must differ from author; proposal hash and live base must still match.",
                requestBody=_body(_object({"body_hash": string}, ("body_hash",))),
            )
        },
        "/metadata/proposals/{proposal_id}/reject": {
            "post": _operation(
                "Reject metadata proposal",
                "Metadata proposals",
                proposal_response,
                errors=(400, 401, 403, 404, 409, 502, 503),
                security=bearer,
                parameters=[proposal_id],
                description=origin_note,
                requestBody=_body(_object({"reason": string})),
            )
        },
        "/metadata/me": {
            "get": _operation(
                "Read metadata session identity",
                "Session",
                _object({"authenticated": {"type": "boolean"}, "user": string}),
                security=cookie,
                errors=(401,),
            )
        },
        "/metadata/logout": {
            "post": _operation(
                "Clear metadata session",
                "Session",
                _object({"authenticated": {"type": "boolean"}}),
                errors=(403,),
                description="Requires an allowed AIND HTTPS Origin; the Panel OAuth session is retained.",
            )
        },
        "/metadata/login": {
            "get": {
                "summary": "Establish metadata session",
                "tags": ["Session"],
                "security": [],
                "description": "Open as a top-level navigation; redirects through Panel OAuth when needed.",
                "parameters": [_parameter("redirect", required=True, description="Allowed AIND HTTPS return URL.")],
                "responses": {
                    "302": {"description": "Redirect to login or return URL"},
                    "400": {"description": "Invalid redirect"},
                    "403": {"description": "Cross-site request denied"},
                },
            }
        },
        "/get-signed-reference/{asset_name}": {
            "get": _operation(
                "Sign an asset's QC metric reference",
                "Media",
                _object({"url": string}),
                parameters=[_parameter("asset_name", "path", True), _parameter("reference", required=True)],
                errors=(400, 403, 404),
            )
        },
        "/upload_metadata": {
            "post": {
                "summary": "Upload temporary metadata",
                "tags": ["Metadata"],
                "security": [],
                "requestBody": _body(arbitrary),
                "responses": {
                    "200": {
                        "description": "Uploaded",
                        "content": {
                            "application/json": {
                                "schema": _object({"status": {"type": "integer"}}),
                            }
                        },
                    },
                    "500": {"description": "Upload or request parsing failed (HTML error response)"},
                },
            }
        },
    }
    return {
        "openapi": "3.0.3",
        "info": {"title": "AIND QC Portal API", "version": __version__},
        "servers": [{"url": "/"}],
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "EntraBearer": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Entra ID identity token for the configured tenant and audience.",
                },
                "MetadataSession": {"type": "apiKey", "in": "cookie", "name": "aind_metadata_session"},
            },
        },
    }


class OpenApiHandler(RequestHandler):
    """Serve the public OpenAPI specification."""

    def get(self):
        """Return the API contract as JSON."""
        self.set_header("Content-Type", "application/json")
        self.write(openapi_spec())


class ApiDocsHandler(RequestHandler):
    """Serve Swagger UI using a pinned upstream distribution."""

    def get(self):
        """Render interactive API documentation."""
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.write("""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIND QC Portal API</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">
</head><body><div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: '/openapi.json', dom_id: '#swagger-ui', deepLinking: true,
validatorUrl: null, persistAuthorization: false});</script>
</body></html>""")
