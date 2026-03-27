exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405 };

  const { name, email, subject, message } = JSON.parse(event.body);

  // Send email using Netlify built-in
  const nodemailer = require('nodemailer');
  
  // Using Gmail SMTP (or your email service)
  const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_PASS
    }
  });

  try {
    // Email TO YOU
    await transporter.sendMail({
      from: process.env.EMAIL_USER,
      to: 'hello@agentixlens.com',
      subject: `[AgentixLens Contact] ${subject}`,
      html: `
        <h2>New Contact Form Submission</h2>
        <p><strong>From:</strong> ${name}</p>
        <p><strong>Email:</strong> ${email}</p>
        <p><strong>Subject:</strong> ${subject}</p>
        <p><strong>Message:</strong></p>
        <p>${message.replace(/\n/g, '<br>')}</p>
      `
    });

    // Confirmation email TO SENDER
    await transporter.sendMail({
      from: process.env.EMAIL_USER,
      to: email,
      subject: 'We received your message - AgentixLens',
      html: `
        <h2>Thanks for contacting AgentixLens!</h2>
        <p>Hi ${name},</p>
        <p>We received your message and will get back to you shortly.</p>
        <p><strong>Your message:</strong> "${subject}"</p>
        <p>Best regards,<br>AgentixLens Team</p>
      `
    });

    return {
      statusCode: 200,
      body: JSON.stringify({ message: 'Email sent successfully' })
    };
  } catch (error) {
    console.error(error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Failed to send email' })
    };
  }
};