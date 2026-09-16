"use server";

import { Resend } from "resend";

const resend = new Resend(process.env.RESEND_API_KEY);

export async function joinWaitlist(formData: FormData) {
  try {
    const email = formData.get("email") as string;

    if (!email || !email.includes("@")) {
      return { success: false, error: "Invalid email address" };
    }

    // 1. Add contact to Resend Audience (if AUDIENCE_ID is provided)
    if (process.env.RESEND_AUDIENCE_ID) {
      await resend.contacts.create({
        email,
        audienceId: process.env.RESEND_AUDIENCE_ID,
      });
    }

    // 2. Send welcome email to the user
    await resend.emails.send({
      from: "Leaka AI <founder@leaka.live>", // Make sure to verify this domain in Resend
      to: email,
      subject: "Welcome to the Leaka AI Waitlist",
      html: `<div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;"><h2>You're on the list!</h2><p>Thanks for your interest in Leaka AI. We are currently onboarding enterprise partners in batches to ensure maximum quality and dedicated support.</p><p>We will be in touch as soon as a spot opens up.</p><p>Best,<br/>Aryan (Founder, Leaka AI)</p></div>`,
    });

    // 3. Send notification to founder
    await resend.emails.send({
      from: "Waitlist Bot <founder@leaka.live>", 
      to: "founder@leaka.live", // Or your actual email
      subject: `New Waitlist Signup: ${email}`,
      html: `<p>A new user just joined the waitlist: <b>${email}</b></p>`,
    });

    return { success: true };
  } catch (error) {
    console.error("Waitlist error:", error);
    return { success: false, error: "Failed to join waitlist. Please try again." };
  }
}

