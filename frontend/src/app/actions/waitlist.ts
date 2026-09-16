"use server";

import { Resend } from "resend";

const resend = new Resend(process.env.RESEND_API_KEY);

export async function joinWaitlist(formData: FormData) {
  try {
    const email = formData.get("email") as string;

    if (!email || !email.includes("@")) {
      return { success: false, error: "Invalid email address" };
    }

    if (process.env.RESEND_AUDIENCE_ID) {
      await resend.contacts.create({
        email,
        audienceId: process.env.RESEND_AUDIENCE_ID,
      });
    }

    const emailHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
      </head>
      <body style="margin: 0; padding: 0; background-color: #0b0f19; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0b0f19; padding: 40px 20px;">
          <tr>
            <td align="center">
              <table width="100%" max-width="600" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 40px; text-align: left;">
                <tr>
                  <td>
                    <div style="font-size: 24px; font-weight: bold; letter-spacing: -0.05em; margin-bottom: 32px; color: #ffffff;">
                      <img src="https://www.leaka.live/leaka-logo.png" alt="Leaka AI" style="height: 24px; vertical-align: middle; margin-right: 12px; filter: brightness(0) invert(1);" />
                      Leaka AI
                    </div>
                    <div style="font-family: monospace; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 16px;">
                      Status: Confirmed
                    </div>
                    <h1 style="font-size: 32px; font-weight: 600; margin: 0 0 24px 0; letter-spacing: -0.02em; line-height: 1.2; color: #ffffff;">
                      You're on the exclusive waitlist.
                    </h1>
                    <p style="color: #94a3b8; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                      Thank you for your interest in <span style="color: #ffffff; font-weight: 500;">Leaka AI</span>.
                    </p>
                    <p style="color: #94a3b8; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                      We are currently onboarding enterprise partners in tightly controlled batches to ensure maximum execution quality, dedicated support, and pristine visual proofing.
                    </p>
                    <p style="color: #94a3b8; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                      Your spot is secured. We will notify you the moment an allocation opens up for your team to start securely testing and scaling your revenue flows.
                    </p>
                    <div style="margin-top: 48px; padding-top: 24px; border-top: 1px solid #1f2937; color: #64748b; font-size: 14px; line-height: 1.5;">
                      Aryan<br/>
                      Founder, Leaka AI
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
      </html>
    `;

    await resend.emails.send({
      from: "Leaka AI <hello@leaka.live>", 
      to: email,
      subject: "Welcome to the Leaka AI Waitlist",
      html: emailHtml,
    });

    return { success: true };
  } catch (error) {
    console.error("Waitlist error:", error);
    return { success: false, error: "Failed to join waitlist. Please try again." };
  }
}

