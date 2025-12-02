import * as React from "react";
import { Html, Body, Container, Text, Heading } from "@react-email/components";

/**
 * Developer notification template for user-event-email (and other services).
 *
 * NOTE:
 * - Dynamic values are expressed as {{tokens}} so Python can perform simple
 *   string replacement at runtime after loading the generated HTML/text.
 * - Keep token names stable; multiple services may rely on them.
 *
 * Visual style is inspired by the OZ homepage:
 * - Primary blue: #1e88e5
 * - Brand font: Montserrat / system-ui
 * - Soft card, subtle border, and clear CTA.
 */
export const DeveloperNotification: React.FC = () => {
  const eventType = "{{event_type}}";
  const listingSlug = "{{listing_slug}}";
  const developerName = "{{developer_name}}";
  const userEmail = "{{user_email}}";

  const primary = "#1e88e5";

  return (
    <Html>
      <Body
        style={{
          fontFamily:
            '"Avenir", -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
          backgroundColor: "#f3f4f6",
          margin: 0,
          padding: "16px 0",
          fontSize: "15px",
          lineHeight: "1.6",
        }}
      >
        <Container
          style={{
            width: "100%",
            maxWidth: "640px",
            margin: "0 auto",
            backgroundColor: "#ffffff",
            borderRadius: "16px",
            border: "1px solid #e5e7eb",
            overflow: "hidden",
            boxShadow:
              "0 18px 45px rgba(15, 23, 42, 0.08), 0 8px 20px rgba(15, 23, 42, 0.06)",
          }}
        >
          {/* Branded header bar with logo (solid color) */}
          <div
            style={{
              backgroundColor: "#1e88e5",
              padding: "18px 20px",
              display: "flex",
              alignItems: "center",
              gap: "12px",
            }}
          >
            <img
              src="https://ozlistings.com/oz-listings-horizontal2-logo-white.webp"
              alt="OZListings"
              width={140}
              height={32}
              style={{ display: "block", maxWidth: "140px", height: "auto" }}
            />
            <div style={{ color: "#bfdbfe" }}>
              <Text
                style={{
                  margin: 0,
                  fontSize: "11px",
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "#bfdbfe",
                }}
              >
                OZListings
              </Text>
              <Heading
                style={{
                  margin: "2px 0 0 0",
                  fontSize: "18px",
                  lineHeight: "1.4",
                  color: "#ffffff",
                  fontWeight: 800,
                }}
              >
                New activity on your OZ listing
              </Heading>
            </div>
          </div>

          {/* Main content */}
          <div
            style={{
              padding: "20px 20px 18px 20px",
            }}
          >
            <Text
              style={{
                margin: "0 0 12px 0",
                fontSize: "15px",
                color: "#4b5563",
              }}
            >
              Hi <span style={{ fontWeight: 600 }}>{developerName || "there"}</span>,
            </Text>

            <Text
              style={{
                margin: "0 0 14px 0",
                fontSize: "15px",
                color: "#111827",
              }}
            >
              Someone who visited your listing{" "}
              <span style={{ fontWeight: 600 }}>{listingSlug}</span>
              {userEmail ? (
                <>
                  {" "}
                  (email:{" "}
                  <span style={{ fontFamily: "monospace" }}>{userEmail}</span>)
                </>
              ) : null}{" "}
              just reached out with a{" "}
              <span style={{ fontWeight: 600 }}>
                {eventType.replace("_", " ")}
              </span>{" "}
              inquiry.
            </Text>

            {/* Highlighted meta box */}
            <div
              style={{
                margin: "0 0 20px 0",
                padding: "12px 14px",
                borderRadius: "12px",
                backgroundColor: "#eff6ff",
                border: "1px solid #bfdbfe",
              }}
            >
              <Text
                style={{
                  margin: 0,
                fontSize: "14px",
                  color: "#1f2933",
                }}
              >
                <strong style={{ color: primary }}>Summary</strong>
              </Text>
              <Text
                style={{
                  margin: "6px 0 0 0",
                  fontSize: "14px",
                  color: "#374151",
                }}
              >
                Type:{" "}
                <span style={{ fontWeight: 600 }}>
                  {eventType.replace("_", " ")}
                </span>
                <br />
                Listing:{" "}
                <span style={{ fontFamily: "monospace" }}>{listingSlug}</span>
                {userEmail ? (
                  <>
                    <br />
                    Contact email:{" "}
                    <span style={{ fontFamily: "monospace" }}>{userEmail}</span>
                  </>
                ) : null}
              </Text>
            </div>

            {/* (CTA button intentionally omitted – see lead via main dashboard navigation) */}
          </div>

          {/* Footer */}
          <div
            style={{
              borderTop: "1px solid #e5e7eb",
              padding: "12px 24px 20px 24px",
              backgroundColor: "#f9fafb",
            }}
          >
            <Text
              style={{
                margin: "0 0 4px 0",
                fontSize: "11px",
                color: "#9ca3af",
              }}
            >
              You are receiving this email because you’re listed as the
              developer contact for this opportunity on OZListings.
            </Text>
            <Text
              style={{
                margin: 0,
                fontSize: "11px",
                color: "#9ca3af",
              }}
            >
              © {new Date().getFullYear()} OZListings. All rights
              reserved.
            </Text>
          </div>
        </Container>
      </Body>
    </Html>
  );
};

