// functions/broadcast.js
const sgMail = require('@sendgrid/mail');

exports.broadcastToEarlyAccess = async (emailContent) => {
  const subscribers = await db.collection('early_access')
    .where('status', '==', 'confirmed')
    .get();

  const emails = subscribers.docs.map(doc => ({
    to: doc.data().email,
    from: 'hello@agentixlens.com',
    subject: 'Updates from AgentixLens',
    html: emailContent
  }));

  await sgMail.send(emails);
};