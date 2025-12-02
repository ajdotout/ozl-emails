import * as React from "react";
import { Html, Body, Container, Text, Heading } from "@react-email/components";

/**
 * Developer notification template for user-event-email (and other services).
 *
 * NOTE:
 * - Dynamic values are expressed as {{tokens}} so Python can perform simple
 *   string replacement at runtime after loading the generated HTML/text.
 * - Keep token names stable; multiple services may rely on them.
 */
export const DeveloperNotification: React.FC = () => {
  const eventType = "{{event_type}}";
  const listingSlug = "{{listing_slug}}";
  const developerName = "{{developer_name}}";
  const userEmail = "{{user_email}}";

  return (
    <Html>
      <Body
        style={{
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          backgroundColor: "#f5f5f5",
          margin: 0,
          padding: "24px 0",
        }}
      >
        <Container
          style={{
            padding: "24px",
            maxWidth: "600px",
            margin: "0 auto",
            backgroundColor: "#ffffff",
            borderRadius: "12px",
            border: "1px solid #e5e7eb",
          }}
        >
          <Heading style={{ marginTop: 0, marginBottom: "16px" }}>
            New {eventType.replace("_", " ")} on {listingSlug}
          </Heading>

          <Text style={{ margin: "0 0 12px 0" }}>
            Hi {developerName || "there"},
          </Text>

          <Text style={{ margin: "0 0 12px 0" }}>
            A user{userEmail ? ` (${userEmail})` : ""} just triggered
            <strong> {eventType.replace("_", " ")} </strong>
            on listing <strong>{listingSlug}</strong>.
          </Text>

          <Text style={{ margin: "0 0 12px 0" }}>
            You can log in to the OZL dashboard to see more details about this
            event and follow up with the prospective investor.
          </Text>

          <Text style={{ margin: "24px 0 0 0", fontSize: "12px", color: "#6b7280" }}>
            You are receiving this email because you are listed as a developer
            contact for this opportunity on Opportunity Zone Logics.
          </Text>
        </Container>
      </Body>
    </Html>
  );
};


