"use server";

import { Resend } from "resend";

const resend = new Resend(process.env.RESEND_API_KEY);

export async function joinWaitlist(formData: FormData) {
  try {
    const email = formData.get("email") as string;

    if (!email || !email.includes("@")) {
      return { success: false, error: "Invalid email address" };
    }

    // 1. Add contact to Resend Audience (CRM)
    if (process.env.RESEND_AUDIENCE_ID) {
      await resend.contacts.create({
        email,
        audienceId: process.env.RESEND_AUDIENCE_ID,
      });
    }

    // 2. Send welcome email to the user
    await resend.emails.send({
      from: "Leaka AI <hello@leaka.live>", 
      to: email,
      subject: "Welcome to the Leaka AI Waitlist",
      html: `<div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;"><h2>You're on the list!</h2><p>Thanks for your interest in Leaka AI. We are currently onboarding enterprise partners in batches to ensure maximum quality and dedicated support.</p><p>We will be in touch as soon as a spot opens up.</p><p>Best,<br/>Aryan (Founder, Leaka AI)</p></div>`,
    });

    return { success: true };
  } catch (error) {
    console.error("Waitlist error:", error);
    return { success: false, error: "Failed to join waitlist. Please try again." };
  }
}

