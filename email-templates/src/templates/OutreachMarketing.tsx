import * as React from "react";
import { Html, Body, Container, Text, Heading, Link, Button, Img } from "@react-email/components";

/**
 * Outreach marketing email template for developers with OZ projects.
 *
 * NOTE:
 * - Dynamic values are expressed as {{tokens}} so Python can perform simple
 *   string replacement at runtime after loading the generated HTML/text.
 * - Keep token names stable; multiple services may rely on them.
 *
 * Visual style matches DeveloperNotification template:
 * - Primary blue: #1e88e5
 * - Brand font: Avenir / system-ui
 * - Soft card, subtle border, and clear CTA.
 */
export const OutreachMarketing: React.FC = () => {
  const developerName = "{{developer_name}}";
  const state = "{{state}}";
  const exampleDealLink = "{{example_deal_link}}";
  const callBookingLink = "{{call_booking_link}}";
  // Optional: Add deal image URL if you want to showcase the property visually
  const dealImageUrl = "{{deal_image_url}}";

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
          {/* Branded header bar with logo */}
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
                Let's accelerate your OZ project
              </Heading>
            </div>
          </div>

          {/* Main content */}
          <div
            style={{
              padding: "20px 20px 18px 20px",
            }}
          >
            {/* Line 1: Personalized greeting */}
            <Text
              style={{
                margin: "0 0 16px 0",
                fontSize: "15px",
                color: "#111827",
              }}
            >
              Hi <span style={{ fontWeight: 600 }}>Abraham</span>, I noticed your Opportunity Zone project at{" "}
              <span style={{ fontWeight: 600 }}>2361 2nd Avenue</span> in{" "}
              <span style={{ fontWeight: 600 }}>East Harlem</span>, New York.
            </Text>

            {/* Line 2: Hook */}
            <Text
              style={{
                margin: "0 0 16px 0",
                fontSize: "15px",
                color: "#111827",
                fontWeight: 500,
              }}
            >
              I think you're doing your fundraising wrong.
            </Text>

            {/* Line 3: Introduction to OZListings */}
            <Text
              style={{
                margin: "0 0 16px 0",
                fontSize: "15px",
                color: "#4b5563",
              }}
            >
              But first, let me introduce myself. I'm Todd Vitzthum, founder of{" "}
              <strong>OZListings</strong>—the premier AI-powered marketplace for
              Opportunity Zone investments. We connect developers like you with
              qualified investors actively seeking OZ deals, streamline your capital
              raise process, and provide comprehensive deal marketing services that
              get your project in front of the right people.
            </Text>

            {/* Line 4: Example deal */}
            <Text
              style={{
                margin: "0 0 12px 0",
                fontSize: "15px",
                color: "#4b5563",
              }}
            >
              Check out one of our example deals:{" "}
              <Link
                href={exampleDealLink || "https://ozlistings.com/listings/oz-recap-fund"}
                style={{
                  color: primary,
                  textDecoration: "underline",
                  fontWeight: 600,
                }}
              >
                OZ Recap Fund
              </Link>
            </Text>

            {/* Deal image showcase - using local image for POC */}
            <div style={{ margin: "0 0 16px 0" }}>
              <Link href={exampleDealLink || "https://ozlistings.com/listings/oz-recap-fund"}>
                <Img
                  src="./OZListingsPromoEmail.png"
                  alt="OZ Recap Fund Deal Preview"
                  width="100%"
                  style={{
                    display: "block",
                    maxWidth: "100%",
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                  }}
                />
              </Link>
            </div>

            {/* Line 5: CTA with hook */}
            <Text
              style={{
                margin: "0 0 16px 0",
                fontSize: "15px",
                color: "#4b5563",
              }}
            >
              Because we recognize smart developers when we see them—and we think
              you're one of them—we're offering a{" "}
              <strong style={{ color: primary }}>complimentary strategy call</strong>{" "}
              for a limited time. Let's discuss how we can accelerate your capital
              raise and connect you with the right investors.
            </Text>

            {/* Spots filling urgency */}
            <Text
              style={{
                margin: "0 0 20px 0",
                fontSize: "14px",
                color: primary,
                fontWeight: 600,
                fontStyle: "italic",
              }}
            >
              Spots are filling fast—only a few complimentary calls remaining this month.
            </Text>

            {/* CTA Button */}
            <div style={{ margin: "24px 0" }}>
              <Button
                href={callBookingLink || "https://ozlistings.com"}
                style={{
                  backgroundColor: primary,
                  color: "#ffffff",
                  padding: "12px 24px",
                  borderRadius: "8px",
                  textDecoration: "none",
                  display: "inline-block",
                  fontWeight: 600,
                  fontSize: "15px",
                }}
              >
                Book Your Complimentary Call
              </Button>
            </div>
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
              This email was sent to you because you're listed as a developer with
              an Opportunity Zone project. If you'd prefer not to receive these
              emails, you can unsubscribe.
            </Text>
            <Text
              style={{
                margin: 0,
                fontSize: "11px",
                color: "#9ca3af",
              }}
            >
              © {new Date().getFullYear()} OZListings. All rights reserved.
            </Text>
          </div>
        </Container>
      </Body>
    </Html>
  );
};

